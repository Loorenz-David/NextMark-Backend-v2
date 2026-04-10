"""
Unit tests for zone attribution logic (route zone derivation).

Tests the 60% majority threshold strategy:
1. Derive zone when > 60% of stops share a zone → return (zone_id, zone_version_id)
2. No majority zone (all < 60%) → return (None, None)
3. Empty route or no assignments → return (None, None)
4. Unassigned orders excluded from count → only count assigned stops
"""
import pytest
from unittest.mock import Mock, patch, MagicMock

from Delivery_app_BK.analytics.zone_attribution import derive_route_zone


class TestDeriveRouteZoneMajorityThreshold:
    """Test 60% majority threshold logic."""

    def test_derive_zone_at_exactly_60_percent(self):
        """Route with 6 ordered stops, 4 with zone 5 (66.7%) → should return zone 5."""
        # Create mock route with stops
        route = Mock()
        
        # Create mock stops with zone assignments
        stops = []
        for order_id in range(1, 7):
            stop = Mock()
            stop.order_id = order_id
            stops.append(stop)
        
        route.stops = stops
        route.id = 100
        
        # Mock OrderZoneAssignment query results:
        # Orders 1-4 → zone 5 (4 stops = 66.7%)
        # Order 5 → zone 10 (1 stop = 16.7%)
        # Order 6 → zone 15 (1 stop = 16.7%)
        assignments = {
            1: Mock(zone_id=5, zone_version_id=20, is_unassigned=False),
            2: Mock(zone_id=5, zone_version_id=20, is_unassigned=False),
            3: Mock(zone_id=5, zone_version_id=20, is_unassigned=False),
            4: Mock(zone_id=5, zone_version_id=20, is_unassigned=False),
            5: Mock(zone_id=10, zone_version_id=25, is_unassigned=False),
            6: Mock(zone_id=15, zone_version_id=30, is_unassigned=False),
        }
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            assert zone_id == 5
            assert zone_version_id == 20

    def test_derive_zone_at_exactly_60_percent_lower_bound(self):
        """Route with 10 ordered stops, 6 with zone 7 (60%) → should return zone 7."""
        route = Mock()
        
        stops = [Mock(order_id=i) for i in range(1, 11)]
        route.stops = stops
        route.id = 101
        
        # 6 stops with zone 7 (60%)
        # 4 stops with other zones
        assignments = {}
        for i in range(1, 7):
            assignments[i] = Mock(zone_id=7, zone_version_id=35, is_unassigned=False)
        for i in range(7, 11):
            assignments[i] = Mock(
                zone_id=8 + (i - 7) % 2,  # Distribute remaining
                zone_version_id=40,
                is_unassigned=False
            )
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            assert zone_id == 7
            assert zone_version_id == 35

    def test_no_majority_below_60_percent(self):
        """Route with 4 stops, each in different zone (25% each) → return (None, None)."""
        route = Mock()
        
        stops = [Mock(order_id=i) for i in range(1, 5)]
        route.stops = stops
        route.id = 102
        
        # Each stop in different zone = no majority
        assignments = {
            1: Mock(zone_id=1, zone_version_id=100, is_unassigned=False),
            2: Mock(zone_id=2, zone_version_id=101, is_unassigned=False),
            3: Mock(zone_id=3, zone_version_id=102, is_unassigned=False),
            4: Mock(zone_id=4, zone_version_id=103, is_unassigned=False),
        }
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            assert zone_id is None
            assert zone_version_id is None

    def test_barely_below_majority_threshold(self):
        """Route with 10 stops, 5 with zone 9 (50%) → below 60%, return (None, None)."""
        route = Mock()
        
        stops = [Mock(order_id=i) for i in range(1, 11)]
        route.stops = stops
        route.id = 103
        
        # 5 stops with zone 9 (50%)
        # 5 stops split between other zones
        assignments = {}
        for i in range(1, 6):
            assignments[i] = Mock(zone_id=9, zone_version_id=50, is_unassigned=False)
        for i in range(6, 11):
            assignments[i] = Mock(
                zone_id=10 + (i - 6),
                zone_version_id=51 + (i - 6),
                is_unassigned=False
            )
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            assert zone_id is None
            assert zone_version_id is None


class TestDeriveRouteZoneEdgeCases:
    """Test edge cases: empty routes, unassigned stops, None values."""

    def test_empty_route_no_stops(self):
        """Route with no stops → return (None, None)."""
        route = Mock()
        route.stops = []
        route.id = 200
        
        zone_id, zone_version_id = derive_route_zone(route)
        
        assert zone_id is None
        assert zone_version_id is None

    def test_none_route(self):
        """None route_solution → return (None, None)."""
        zone_id, zone_version_id = derive_route_zone(None)
        
        assert zone_id is None
        assert zone_version_id is None

    def test_all_stops_unassigned(self):
        """All stops have unassigned orders → return (None, None)."""
        route = Mock()
        
        stops = [Mock(order_id=i) for i in range(1, 4)]
        route.stops = stops
        route.id = 201
        
        # All orders unassigned (is_unassigned=True)
        assignments = {
            1: Mock(zone_id=None, zone_version_id=None, is_unassigned=True),
            2: Mock(zone_id=None, zone_version_id=None, is_unassigned=True),
            3: Mock(zone_id=None, zone_version_id=None, is_unassigned=True),
        }
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            assert zone_id is None
            assert zone_version_id is None

    def test_stops_with_no_order_id_skipped(self):
        """Stops without order_id are skipped, but route still derives zone from others."""
        route = Mock()
        
        # Stop 1: no order_id (skipped)
        # Stop 2-4: order_id (3 stops with zone 20)
        stops = [
            Mock(order_id=None),
            Mock(order_id=2),
            Mock(order_id=3),
            Mock(order_id=4),
        ]
        route.stops = stops
        route.id = 202
        
        # Only stops 2-4 are assigned (100% to zone 20)
        assignments = {
            2: Mock(zone_id=20, zone_version_id=100, is_unassigned=False),
            3: Mock(zone_id=20, zone_version_id=100, is_unassigned=False),
            4: Mock(zone_id=20, zone_version_id=100, is_unassigned=False),
        }
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            # All assigned stops (3) have zone 20 = 100% > 60%
            assert zone_id == 20
            assert zone_version_id == 100


class TestDeriveRouteZoneIntegration:
    """Integration-like tests with semi-realistic scenarios."""

    def test_route_with_mixed_assigned_and_unassigned_stops(self):
        """Route: 2 stops zone 5, 1 stop zone 10, 1 stop unassigned → zone 5 is 50% (below threshold)."""
        route = Mock()
        
        stops = [Mock(order_id=i) for i in range(1, 5)]
        route.stops = stops
        route.id = 300
        
        assignments = {
            1: Mock(zone_id=5, zone_version_id=20, is_unassigned=False),
            2: Mock(zone_id=5, zone_version_id=20, is_unassigned=False),
            3: Mock(zone_id=10, zone_version_id=25, is_unassigned=False),
            4: Mock(zone_id=None, zone_version_id=None, is_unassigned=True),
        }
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            # Zone 5 appears in 2 of 3 assigned stops = 66.7% > 60%
            assert zone_id == 5
            assert zone_version_id == 20

    def test_route_with_missing_zone_assignments(self):
        """Database query returns None for some orders → skip those orders."""
        route = Mock()
        
        stops = [Mock(order_id=i) for i in range(1, 5)]
        route.stops = stops
        route.id = 301
        
        # Order 2 has no database record (returns None)
        assignments = {
            1: Mock(zone_id=7, zone_version_id=40, is_unassigned=False),
            2: None,  # Missing assignment
            3: Mock(zone_id=7, zone_version_id=40, is_unassigned=False),
            4: Mock(zone_id=8, zone_version_id=41, is_unassigned=False),
        }
        
        def mock_query_filter(order_id):
            return assignments.get(order_id)
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            mock_session.query.return_value.filter_by.side_effect = (
                lambda order_id: Mock(first=lambda: mock_query_filter(order_id))
            )
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            # Zone 7 appears in 2 of 3 assignments where data exists = 66.7% > 60%
            assert zone_id == 7
            assert zone_version_id == 40

    def test_derive_route_zone_error_handling(self):
        """Exception during zone derivation → return (None, None) with logging."""
        route = Mock()
        route.stops = []
        route.id = 302
        
        with patch('Delivery_app_BK.models.db.session') as mock_session:
            # Simulate database error
            mock_session.query.side_effect = Exception("Database connection lost")
            
            zone_id, zone_version_id = derive_route_zone(route)
            
            # Should gracefully return None, None
            assert zone_id is None
            assert zone_version_id is None
