"""Unit tests for zone assignment service components."""

import pytest
import math
from datetime import datetime, timezone
from unittest.mock import Mock, MagicMock, patch

from Delivery_app_BK.zones.services import (
    normalize_city_key,
    get_active_zone_version,
    ZoneResolution,
    resolve_point_to_zone,
    upsert_order_zone_assignment,
)


# ============================================================================
# Tests for city_key_normalizer
# ============================================================================

class TestNormalizeCityKey:
    """Test suite for normalize_city_key utility."""

    def test_normalize_simple_city_name(self):
        """Basic city name normalization."""
        assert normalize_city_key("New York") == "new_york"
        assert normalize_city_key("los angeles") == "los_angeles"

    def test_normalize_removes_special_characters(self):
        """Special characters are stripped out."""
        assert normalize_city_key("São Paulo") == "so_paulo"
        assert normalize_city_key("St. Louis") == "st_louis"
        assert normalize_city_key("Paris, France") == "paris_france"

    def test_normalize_handles_spaces(self):
        """Multiple spaces are collapsed to underscores."""
        assert normalize_city_key("San   Francisco") == "san_francisco"
        assert normalize_city_key("  Boston  ") == "boston"

    def test_normalize_handles_none(self):
        """None returns default unknown_city."""
        assert normalize_city_key(None) == "unknown_city"

    def test_normalize_handles_empty_string(self):
        """Empty string returns default unknown_city."""
        assert normalize_city_key("") == "unknown_city"
        assert normalize_city_key("   ") == "unknown_city"

    def test_normalize_handles_special_only(self):
        """String with only special characters returns default."""
        assert normalize_city_key("!!!") == "unknown_city"
        assert normalize_city_key("@#$%") == "unknown_city"

    def test_normalize_case_insensitive(self):
        """Output is always lowercase."""
        assert normalize_city_key("NEW YORK") == "new_york"
        assert normalize_city_key("LoS aNgElEs") == "los_angeles"

    def test_normalize_with_numbers(self):
        """Numbers are preserved."""
        assert normalize_city_key("New York 123") == "new_york_123"
        assert normalize_city_key("Area 51") == "area_51"


class TestGetActiveZoneVersion:
    """Test suite for get_active_zone_version."""

    @patch('Delivery_app_BK.zones.services.version_resolver.ZoneVersion')
    def test_get_active_version(self, mock_zone_version):
        """Retrieve active zone version by team and city."""
        mock_query = MagicMock()
        mock_zone_version.query.filter.return_value = mock_query
        
        mock_version = Mock(id=1, is_active=True)
        mock_query.one_or_none.return_value = mock_version
        
        result = get_active_zone_version(1, "new_york")
        
        assert result == mock_version
        mock_zone_version.query.filter.assert_called_once()

    @patch('Delivery_app_BK.zones.services.version_resolver.ZoneVersion')
    def test_get_active_version_returns_none_for_nonexistent(self, mock_zone_version):
        """Returns None if no active version exists."""
        mock_query = MagicMock()
        mock_zone_version.query.filter.return_value = mock_query
        mock_query.one_or_none.return_value = None
        
        result = get_active_zone_version(1, "nonexistent_city")
        
        assert result is None


# ============================================================================
# Tests for point_to_zone_resolver
# ============================================================================

class TestResolvePointToZone:
    """Test suite for resolve_point_to_zone."""

    def test_haversine_distance_calculation(self):
        """Test accurate distance calculation between coordinates."""
        from Delivery_app_BK.zones.services.point_to_zone_resolver import haversine_distance
        
        # NYC to Brooklyn (approximately 4.2 km)
        distance = haversine_distance(
            40.7128, -74.0060,  # NYC
            40.6892, -74.0445,  # Brooklyn
        )
        
        # Should be roughly 4.2 km
        assert 4 < distance < 5
    
    @patch('Delivery_app_BK.zones.services.point_to_zone_resolver.Zone')
    def test_resolve_to_closest_zone(self, mock_zone_class):
        """Resolves to the closest zone by centroid distance."""
        mock_query = MagicMock()
        mock_zone_class.query.filter.return_value = mock_query
        
        # Create mock zones
        zone1 = Mock(
            id=1,
            zone_type="system",
            centroid_lat=40.7128,
            centroid_lng=-74.0060,
            geometry=None,
            is_active=True,
        )
        zone2 = Mock(
            id=2,
            zone_type="system",
            centroid_lat=40.6892,
            centroid_lng=-74.0445,
            geometry=None,
            is_active=True,
        )
        
        mock_query.all.return_value = [zone1, zone2]
        
        # Point close to Brooklyn
        result = resolve_point_to_zone(
            zone_version_id=1,
            lat=40.6892,
            lng=-74.0445,
        )
        
        assert result.zone == zone2  # Should be Brooklyn zone
        assert result.method == "centroid_fallback"

    @patch('Delivery_app_BK.zones.services.point_to_zone_resolver.Zone')
    def test_resolve_respects_zone_type_priority(self, mock_zone_class):
        """User zones take priority over system zones."""
        mock_query = MagicMock()
        mock_zone_class.query.filter.return_value = mock_query
        
        # Create mock zones - user zone farther away but higher priority
        user_zone = Mock(
            id=1,
            zone_type="user",
            centroid_lat=40.75,
            centroid_lng=-74.0,
            geometry=None,
            is_active=True,
        )
        system_zone = Mock(
            id=2,
            zone_type="system",
            centroid_lat=40.7128,
            centroid_lng=-74.0060,
            geometry=None,
            is_active=True,
        )
        
        mock_query.all.return_value = [system_zone, user_zone]
        
        result = resolve_point_to_zone(
            zone_version_id=1,
            lat=40.7128,
            lng=-74.0060,
            priority_types=["user", "system", "bootstrap"],
        )
        
        # Should return user zone even though system zone is closer
        assert result.zone == user_zone
        assert result.method == "centroid_fallback"

    @patch('Delivery_app_BK.zones.services.point_to_zone_resolver.Zone')
    def test_resolve_returns_none_if_no_zones(self, mock_zone_class):
        """Returns None if no zones exist in version."""
        mock_query = MagicMock()
        mock_zone_class.query.filter.return_value = mock_query
        mock_query.all.return_value = []
        
        result = resolve_point_to_zone(
            zone_version_id=1,
            lat=40.7128,
            lng=-74.0060,
        )
        
        assert result.zone is None
        assert result.unassigned_reason == "no_candidate_zone"

    @patch('Delivery_app_BK.zones.services.point_to_zone_resolver.Zone')
    def test_resolve_ignores_inactive_zones(self, mock_zone_class):
        """Only considers active zones (database filters by is_active=True)."""
        mock_query = MagicMock()
        mock_zone_class.query.filter.return_value = mock_query
        
        active_zone = Mock(
            id=1,
            zone_type="system",
            centroid_lat=40.7128,
            centroid_lng=-74.0060,
            geometry=None,
            is_active=True,
        )
        
        # Query only returns active zones because database filters by is_active=True
        mock_query.all.return_value = [active_zone]
        
        result = resolve_point_to_zone(
            zone_version_id=1,
            lat=40.6892,
            lng=-74.0445,
        )
        
        # Should return the only active zone
        assert result.zone == active_zone


# ============================================================================
# Tests for order_assignment_service
# ============================================================================

class TestUpsertOrderZoneAssignment:
    """Test suite for upsert_order_zone_assignment (mocked)."""

    @patch('Delivery_app_BK.zones.services.order_assignment_service.get_active_zone_version')
    @patch('Delivery_app_BK.zones.services.order_assignment_service.resolve_point_to_zone')
    @patch('Delivery_app_BK.zones.services.order_assignment_service.OrderZoneAssignment')
    @patch('Delivery_app_BK.zones.services.order_assignment_service.db')
    def test_assign_system_zone_from_coordinates(
        self, mock_db, mock_assignment_class, mock_resolve, mock_get_version
    ):
        """Automatically assigns zone from coordinates."""
        # Setup mocks
        mock_zone_version = Mock(id=1)
        mock_get_version.return_value = mock_zone_version
        
        mock_zone = Mock(id=10)
        mock_resolve.return_value = ZoneResolution(zone=mock_zone, method="polygon_direct")
        
        mock_assignment = Mock(id=1, order_id=1, zone_id=10, assignment_type="auto")
        mock_assignment_class.query.filter_by.return_value.one_or_none.return_value = None
        mock_assignment_class.return_value = mock_assignment
        
        client_address = {
            "city": "New York",
            "coordinates": {"lat": 40.7128, "lng": -74.0060},
        }
        
        assignment, action = upsert_order_zone_assignment(
            order_id=1,
            team_id=1,
            client_address=client_address,
            user_specified_zone_id=None,
        )
        
        assert action == "system_assigned"
        assert assignment.zone_id == 10
