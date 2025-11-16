import { type RouteConfig, index, route } from "@react-router/dev/routes";

export default [
  index("routes/_index.tsx"),
  route("api/download/:id", "routes/api.download.$id.tsx"),
  route("api/poll", "routes/api.poll.ts"),
] satisfies RouteConfig;
