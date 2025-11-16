import { redirect } from "react-router";
import { getSession } from "./session.js";

/**
 * Checks if the user is authenticated
 */
export async function isAuthenticated(request: Request): Promise<boolean> {
  const session = await getSession(request.headers.get("Cookie"));
  return session.get("authenticated") === true;
}

/**
 * Requires authentication, throws redirect to /login if not authenticated
 */
export async function requireAuth(request: Request): Promise<void> {
  const authenticated = await isAuthenticated(request);
  if (!authenticated) {
    throw redirect("/login");
  }
}

