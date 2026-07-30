# API authentication

All internal API calls require a **Bearer token** in the `Authorization` header.

## Getting a token

1. Log in to the developer portal.
2. Create an API key scoped to your team.
3. Store the key in your password manager — never commit it to git.

## Example

```
Authorization: Bearer YOUR_API_KEY
```

## Rate limits

- Staging: 100 requests/minute
- Production: 1000 requests/minute

Rotate keys every **90 days**. Report leaked keys to security immediately.
