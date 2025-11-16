import { redirect, type ActionFunctionArgs, type LoaderFunctionArgs } from "react-router";
import { getSession, commitSession } from "../lib/session.js";
import { isAuthenticated } from "../lib/auth.js";

export async function loader({ request }: LoaderFunctionArgs) {
  // If already authenticated, redirect to home
  if (await isAuthenticated(request)) {
    throw redirect("/");
  }
  return null;
}

export async function action({ request }: ActionFunctionArgs) {
  const formData = await request.formData();
  const password = formData.get("password") as string | null;

  if (!password) {
    return { error: "Password is required" };
  }

  const expectedPassword = process.env.PASSWORD;
  if (!expectedPassword) {
    console.error("PASSWORD environment variable is not set");
    return { error: "Server configuration error" };
  }

  if (password === expectedPassword) {
    const session = await getSession(request.headers.get("Cookie"));
    session.set("authenticated", true);
    
    // Redirect to home with session cookie
    throw redirect("/", {
      headers: {
        "Set-Cookie": await commitSession(session),
      },
    });
  }

  return { error: "Invalid password" };
}

export default function Login() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign in to YouTube Downloader
          </h2>
        </div>
        <form method="post" className="mt-8 space-y-6">
          <div>
            <label htmlFor="password" className="sr-only">
              Password
            </label>
            <input
              id="password"
              name="password"
              type="password"
              required
              className="appearance-none rounded-md relative block w-full px-3 py-2 border border-gray-300 placeholder-gray-500 text-gray-900 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
              placeholder="Enter password"
            />
          </div>

          <div>
            <button
              type="submit"
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              Sign in
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

