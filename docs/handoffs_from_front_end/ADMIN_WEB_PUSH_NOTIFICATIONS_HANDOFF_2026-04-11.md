# Admin Web Push Notifications Handoff

## Goal

Enable browser push notifications for the admin app so that:

1. an authenticated admin user can opt in to notifications
2. the browser creates a push subscription using a VAPID public key
3. the frontend sends that subscription to the backend
4. the backend persists the subscription against the authenticated admin user
5. when a relevant admin notification is emitted, the backend sends a real Web Push message to the browser subscription
6. clicking the notification opens or focuses the admin app and routes the user to the correct target

At the moment, the frontend flow is blocked by a missing env value:

```text
VITE_WEB_PUSH_PUBLIC_KEY
```

This is not an arbitrary key. It must be the VAPID public key that matches the private key used by the backend push sender.

## Current Frontend Behavior

Frontend already contains a working browser-side subscription flow.

Relevant files:

- `admin-app/src/realtime/notifications/adminWebPush.runtime.ts`
- `admin-app/src/realtime/notifications/adminWebPush.controller.ts`
- `admin-app/src/realtime/notifications/AdminNotificationsPushProvider.tsx`
- `admin-app/src/realtime/notifications/adminWebPush.api.ts`
- `admin-app/public/admin-notifications-sw.js`

### What the frontend currently does

1. checks browser support for `serviceWorker`, `PushManager`, and `Notification`
2. requests notification permission
3. reads `import.meta.env.VITE_WEB_PUSH_PUBLIC_KEY`
4. subscribes with:

```ts
registration.pushManager.subscribe({
  userVisibleOnly: true,
  applicationServerKey: decodeBase64Url(WEB_PUSH_PUBLIC_KEY),
});
```

5. serializes the subscription and sends it to:
   - `POST /notifications/push-subscriptions`
   - `DELETE /notifications/push-subscriptions`
6. receives push payloads in the service worker
7. shows a browser notification
8. on click, focuses or opens the app and forwards launch payload into the SPA

### Current frontend subscription payload

The frontend POST payload is:

```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/...",
  "expirationTime": null,
  "keys": {
    "p256dh": "base64...",
    "auth": "base64..."
  },
  "subscription": {
    "endpoint": "...",
    "expirationTime": null,
    "keys": {
      "p256dh": "...",
      "auth": "..."
    }
  },
  "userAgent": "Mozilla/5.0 ..."
}
```

`subscription` is included so the backend can store or replay the full browser-native subscription object if needed.

## What Backend Needs To Provide

## 1. VAPID Key Pair

Backend must own the Web Push VAPID key pair.

Required outcome:

- generate one VAPID key pair per environment
- keep the private key on the backend only
- expose the matching public key to the frontend environment as `VITE_WEB_PUSH_PUBLIC_KEY`

### Required env model

Backend should define something equivalent to:

```dotenv
WEB_PUSH_VAPID_PUBLIC_KEY=<base64url public key>
WEB_PUSH_VAPID_PRIVATE_KEY=<base64url private key>
WEB_PUSH_VAPID_SUBJECT=mailto:team@example.com
```

Then deployment or frontend build wiring should set:

```dotenv
VITE_WEB_PUSH_PUBLIC_KEY=<same value as WEB_PUSH_VAPID_PUBLIC_KEY>
```

Important:

- `VITE_WEB_PUSH_PUBLIC_KEY` must exactly match the public key paired with the backend private key
- if keys do not match, browser subscription may succeed but push delivery will fail

## 2. Subscription Persistence API

The frontend already expects these endpoints:

### Upsert subscription

`POST /notifications/push-subscriptions`

Expected behavior:

- require authenticated admin user
- validate payload shape
- upsert by `endpoint`
- associate subscription with authenticated user and workspace/app scope if relevant
- store enough metadata to support send, cleanup, and audit

Suggested stored fields:

- `user_id`
- `endpoint`
- `p256dh`
- `auth`
- `expiration_time`
- `subscription_json`
- `user_agent`
- `is_active`
- `last_seen_at`
- `created_at`
- `updated_at`

### Delete subscription

`DELETE /notifications/push-subscriptions`

Expected request body:

```json
{
  "endpoint": "https://fcm.googleapis.com/fcm/send/..."
}
```

Expected behavior:

- require authenticated admin user
- delete or deactivate the matching subscription owned by that user
- return success even if the record is already absent, to keep frontend cleanup idempotent

## 3. Web Push Sender

Backend must implement actual Web Push delivery using the stored subscription plus the VAPID private key.

Required behavior:

1. select target subscriptions for the intended admin user or users
2. send a standards-compliant Web Push message using the stored subscription
3. use the VAPID private key and subject
4. remove or deactivate subscriptions that are no longer valid

Typical invalidation cases:

- `404`
- `410`
- provider-specific expired subscription responses

Those invalid subscriptions should be cleaned up automatically so the system does not keep retrying dead endpoints.

## 4. Push Payload Contract

The service worker already accepts JSON payloads. The backend should send payloads that align with this structure:

```json
{
  "notification": {
    "notification_id": "uuid-or-stable-id",
    "occurred_at": "2026-04-11T12:00:00Z",
    "title": "New order case message",
    "description": "Order case #123 has a new message",
    "target": {
      "kind": "order_case_chat",
      "params": {
        "orderCaseId": 123
      }
    }
  }
}
```

### Payload requirements

- `notification_id`: stable identifier for de-duplication / tagging
- `occurred_at`: ISO timestamp
- `title`: visible notification title
- `description`: visible notification body text
- `target`: destination contract used by the SPA after click

The service worker currently resolves the displayed content from:

- `payload.notification.title` or `payload.title`
- `payload.notification.description` or `payload.body` or `payload.description`

The click routing flow expects:

```json
{
  "notification_id": "...",
  "occurred_at": "...",
  "target": {
    "kind": "...",
    "params": {}
  }
}
```

If backend payloads omit that launch contract, click navigation will degrade even if the notification is shown successfully.

## 5. Notification Target Contract Alignment

Backend should only emit `target.kind` values supported by the admin app notification target handlers.

Frontend currently contains explicit handlers for:

- `order_detail`
- `order_case_detail`
- `order_case_chat`
- `local_delivery_workspace`

Examples:

```json
{
  "target": {
    "kind": "order_detail",
    "params": {
      "orderId": 456
    }
  }
}
```

```json
{
  "target": {
    "kind": "local_delivery_workspace",
    "params": {
      "planId": 789
    }
  }
}
```

If backend wants to introduce new target kinds, that requires an explicit frontend addition.

## 6. Delivery Trigger Integration

Backend needs to decide which domain events produce a push notification.

Recommended flow:

1. domain event occurs
2. backend creates a persistent in-app notification record
3. backend resolves eligible admin recipients
4. backend loads active web push subscriptions for those recipients
5. backend sends Web Push payloads
6. backend marks invalid subscriptions inactive when provider response indicates they are dead

This should run in backend async infrastructure, not inline in request/response code, unless the current architecture requires a first small implementation step.

## Suggested Backend Plan

## Phase 1. Infrastructure and config

1. Add VAPID key configuration to backend env.
2. Decide the library used to send Web Push.
3. Define how the frontend build receives the public key for each environment.

Deliverable:

- backend can read VAPID public/private key and subject
- frontend deployment gets `VITE_WEB_PUSH_PUBLIC_KEY`

## Phase 2. Subscription persistence

1. Add subscription table/model.
2. Add authenticated `POST /notifications/push-subscriptions`.
3. Add authenticated `DELETE /notifications/push-subscriptions`.
4. Add validation and idempotent upsert/delete behavior.

Deliverable:

- admin app can enable notifications without server-side contract failures

## Phase 3. Push delivery

1. Build a push send service that accepts:
   - recipient user ids
   - title
   - description
   - notification metadata
   - target
2. Send real Web Push messages to saved subscriptions.
3. Handle invalid subscription cleanup.

Deliverable:

- a backend command or async job can send a notification that appears in the browser

## Phase 4. Event integration

1. Attach push delivery to selected notification-producing events.
2. Make sure the payload contains a supported frontend `target`.
3. Confirm click-through routing works end to end.

Deliverable:

- production notification events reach subscribed admin browsers and open the right page

## Backend Acceptance Criteria

The backend work should be considered complete when all of the following are true:

1. the frontend receives a valid `VITE_WEB_PUSH_PUBLIC_KEY`
2. enabling notifications no longer fails with `Missing VITE_WEB_PUSH_PUBLIC_KEY.`
3. `POST /notifications/push-subscriptions` stores a browser subscription for the authenticated admin
4. `DELETE /notifications/push-subscriptions` removes or deactivates it
5. backend can send a test Web Push to a stored subscription
6. the browser displays the notification while the app is open or backgrounded
7. clicking the notification focuses or opens the admin app
8. the app routes correctly using the payload `target`
9. invalid or expired subscriptions are cleaned up automatically

## Open Questions For Backend Team

These should be resolved explicitly before implementation drifts:

1. Which authenticated principal owns a push subscription: admin user, workspace membership, or both?
2. Should one user be allowed multiple active subscriptions across browsers/devices? Recommended answer: yes.
3. Is the app deployed behind a single origin per environment, and does that origin match the service worker scope?
4. Which backend event pipeline should own push delivery: existing notification system, async worker queue, or a new dedicated sender?
5. Which events should send push vs. only in-app notifications?

## Short Summary

Frontend is already prepared to:

- request browser notification permission
- create a push subscription with a VAPID public key
- persist that subscription to the backend
- display push notifications via service worker
- route notification clicks into the SPA

The missing backend responsibilities are:

- own and configure the VAPID key pair
- expose the public key to frontend build/runtime
- persist subscriptions
- send real Web Push messages
- clean up dead subscriptions
- emit payloads that match the admin notification click contract
