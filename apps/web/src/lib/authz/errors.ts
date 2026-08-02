import type { PermissionKey } from "./permissions";

export class AuthError extends Error {
  status: number;
  code: "UNAUTHENTICATED" | "FORBIDDEN";

  constructor(
    message: string,
    status: 401 | 403,
    code: "UNAUTHENTICATED" | "FORBIDDEN",
  ) {
    super(message);
    this.name = "AuthError";
    this.status = status;
    this.code = code;
  }
}

export function unauthorized(message = "Unauthorized") {
  return new AuthError(message, 401, "UNAUTHENTICATED");
}

export function forbidden(permission?: PermissionKey) {
  return new AuthError(
    permission ? `Missing permission: ${permission}` : "Forbidden",
    403,
    "FORBIDDEN",
  );
}
