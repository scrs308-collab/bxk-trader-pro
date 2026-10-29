# Subscriber messaging

Open **Messages** in the dashboard header or `/messages`.

- Private inbox: each subscriber has a private thread with the BXK owner team. Subscribers cannot discover, read, or post to another subscriber's thread. Owners can select a subscriber, read history, and reply. No subscriber email addresses appear in chat.
- Subscriber lounge: eligible members and owners can exchange group messages. Owner messages are labeled. Owners can remove messages; text is erased, and sender, time, and moderation metadata remain.
- Access: active database accounts only. When subscription enforcement is enabled, existing subscription rules apply, including trials/manual access and owner bypass. When disabled, active beta/viewer accounts can participate. Disabled accounts lose access immediately.
- In-app notifications: dashboard unread badge and per-conversation counts. The messenger refreshes every 10 seconds while visible; dashboard badge every 30 seconds. This release sends no email, SMS, push notifications, or automated messages.
- Text only, maximum 4,000 characters, 20 sends per minute per user. Sending uses a persisted idempotency key to protect retries. History loads in pages of 50; owner subscriber search is also paginated.
- Browser message content is rendered as text. Writes require same-origin browser requests, and all reads/writes enforce database identity and account access.

Migration `c34d56e78f90` adds `chat_messages` and `chat_read_states`. It does not change users, subscriptions, broker settings, orders, or reserves. Deployment applies it through the existing Alembic pre-deploy command. Rollback of application code can leave the additive tables in place; downgrading this migration removes message history.

Validation: API isolation, two-way delivery, group access, unread positions, moderation, pagination, duplicate retries, rate limiting, invalid input, cross-origin rejection, inactive/expired access, and migration round-trip preservation of users.
