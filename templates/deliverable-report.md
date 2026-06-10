# Deliverable Report Template

Use this final-report block whenever a task creates or modifies user-facing file deliverables.

```text
Deliverables:
- <file-name> — <purpose> — verified: <exists/content checked/format checked/etc.> — attachment: <native|ready|not attached: reason>
```

Checklist before reporting:

1. Verify the file exists before claiming it is ready.
2. For media/generated assets, check basic expected properties when practical: size, duration, format, or content readback.
3. Include file name, purpose, and verification status in the final report.
4. On Slack/Telegram, attach customer-facing artifacts natively when safe and supported, using `MEDIA:/absolute/path` or `send_message` with media paths.
5. Do not automatically attach temporary files, credentials, tokens, secret-bearing logs, or private/sensitive artifacts; ask first when ambiguous.
6. If native attachment delivery is unavailable or fails, state the fallback path and retry/alternate-delivery status.

Telegram/Slack native attachment line when appropriate:

```text
MEDIA:/absolute/path/to/customer-deliverable.ext
```
