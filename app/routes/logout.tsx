import { redirect, type ActionFunctionArgs, type LoaderFunctionArgs } from "react-router";
import { getSession, destroySession } from "../lib/session.js";

export async function loader({ request }: LoaderFunctionArgs) {
  const session = await getSession(request.headers.get("Cookie"));
  
  // Destroy session and redirect to login
  throw redirect("/login", {
    headers: {
      "Set-Cookie": await destroySession(session),
    },
  });
}

export async function action({ request }: ActionFunctionArgs) {
  const session = await getSession(request.headers.get("Cookie"));
  
  // Destroy session and redirect to login
  throw redirect("/login", {
    headers: {
      "Set-Cookie": await destroySession(session),
    },
  });
}

