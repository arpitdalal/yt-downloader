import type { LoaderFunctionArgs } from "react-router";
import { DownloadService } from "../lib/download-service.js";
import type { QueueStatus } from "../lib/types.js";

export async function loader({ request }: LoaderFunctionArgs) {
  const url = new URL(request.url);
  const downloadId = url.searchParams.get("downloadId");

  try {
    const queueStatus = await DownloadService.getQueueStatus();

    let queuePosition: number | undefined;
    let estimatedWaitMinutes: number | undefined;

    if (downloadId) {
      const id = parseInt(downloadId);
      if (!isNaN(id)) {
        queuePosition = await DownloadService.getQueuePosition(id);

        // Estimate wait time based on queue position and average download time
        // Assuming average download takes 5 minutes
        const averageDownloadTime = 5;
        estimatedWaitMinutes = queuePosition * averageDownloadTime;
      }
    }

    const result: QueueStatus = {
      ...queueStatus,
      queue_position: queuePosition,
      estimated_wait_minutes: estimatedWaitMinutes,
    };

    return result;
  } catch (error) {
    return {
      total: 0,
      pending: 0,
      downloading: 0,
      completed: 0,
      failed: 0,
    };
  }
}
