# Contracts

Contracts are authored before endpoint or worker implementation. They define
public HTTP payloads, stable error shapes, outbox events, shared domain DTOs,
and state-machine values. Backend modules and frontend clients consume these
contracts; contract changes require versioning and compatibility review.
