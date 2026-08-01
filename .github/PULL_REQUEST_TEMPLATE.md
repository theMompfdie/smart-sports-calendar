# Pull Request

## Summary

Describe the purpose of this change and what has been implemented.

## Type of Change

- [ ] Bug fix
- [ ] New feature
- [ ] Configuration change
- [ ] Documentation update
- [ ] Dependency update
- [ ] Refactoring
- [ ] Security improvement
- [ ] Release preparation

## Changes

Describe the relevant technical changes.

- 
- 
- 

## Testing

Describe how the change was tested.

- [ ] Python application starts successfully
- [ ] Docker image builds successfully
- [ ] Docker Compose configuration is valid
- [ ] Container health check passes
- [ ] Persistent SQLite data remains available
- [ ] Tested locally with Docker Desktop
- [ ] Tested in Portainer
- [ ] Documentation was updated where required

## Docker Validation

Commands used for validation:

```bash
docker compose config
docker compose build
docker compose up -d
docker compose ps
docker compose logs
```

## Security Review

- [ ] No credentials, tokens, passwords, or certificates were committed
- [ ] No production data was committed
- [ ] The container continues to run as a non-root user
- [ ] New environment variables are documented in `.env.example`
- [ ] New dependencies have been reviewed

## Database Impact

- [ ] No database changes
- [ ] Database schema changed
- [ ] Data migration required

Describe database changes or migration requirements:

```text
Not applicable.
```

## Deployment Impact

- [ ] No deployment changes
- [ ] Dockerfile changed
- [ ] Docker Compose changed
- [ ] Portainer configuration changed
- [ ] Manual deployment action required

Describe any required deployment steps:

```text
Not applicable.
```

## Related Issues

Reference related issues using:

```text
Closes #<issue-number>
```

## Checklist

- [ ] Changes are committed to the correct branch
- [ ] Commit messages are clear
- [ ] Code and configuration were reviewed
- [ ] Tests completed successfully
- [ ] Documentation is current
- [ ] The pull request is ready for merge