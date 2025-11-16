import { data, type LoaderFunctionArgs } from "react-router";
import { DownloadService } from "../lib/download-service.js";
import { validateSameOrigin, handleOptionsRequest } from "../lib/cors.js";

export async function loader({ request }: LoaderFunctionArgs) {
  // Handle OPTIONS preflight
  const optionsResponse = handleOptionsRequest(request);
  if (optionsResponse) return optionsResponse;

  // Validate same-origin
  validateSameOrigin(request);

  const url = new URL(request.url);
  const page = parseInt(url.searchParams.get("page") || "1");
  const limit = 10;
  const offset = (page - 1) * limit;

  try {
    const [downloads, queueStatus] = await Promise.all([
      DownloadService.getAllDownloads(limit, offset),
      DownloadService.getQueueStatus(),
    ]);

    return { downloads, queueStatus, currentPage: page };
  } catch (error) {
    console.error("Error in poll endpoint:", error);
    return data(
      {
        downloads: [],
        queueStatus: {
          total: 0,
          pending: 0,
          downloading: 0,
          completed: 0,
          failed: 0,
        },
        currentPage: page,
      },
      { status: 500 }
    );
  }
}

