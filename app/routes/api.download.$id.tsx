import type { LoaderFunctionArgs } from "react-router";
import { DownloadService } from "../lib/download-service.js";
import { createReadStream, statSync, existsSync, readdirSync } from "node:fs";
import { Readable } from "node:stream";
import path from "node:path";
import { validateSameOrigin, handleOptionsRequest } from "../lib/cors.js";

export async function loader({ params, request }: LoaderFunctionArgs) {
  // Handle OPTIONS preflight
  const optionsResponse = handleOptionsRequest(request);
  if (optionsResponse) return optionsResponse;

  // Validate same-origin
  validateSameOrigin(request);

  const downloadId = parseInt(params.id || "", 10);

  if (isNaN(downloadId)) {
    throw new Response("Invalid download ID", { status: 400 });
  }

  const download = await DownloadService.getDownloadById(downloadId);

  if (!download) {
    throw new Response("Download not found", { status: 404 });
  }

  if (download.status !== "COMPLETED") {
    throw new Response("Download not completed", { status: 400 });
  }

  // Get file path from database
  let filePath = download.filePath;
  if (!filePath) {
    throw new Response("File path not found", { status: 404 });
  }

  // If the stored path is a .part file, try to find the complete file
  if (filePath.endsWith('.part') || filePath.endsWith('.ytdl')) {
    console.log(`⚠️ Stored path is a .part file for download ${downloadId}, searching for complete file...`);
    
    // Try to find the complete file in the same directory
    const dir = path.dirname(filePath);
    const baseName = path.basename(filePath, path.extname(filePath));
    const videoId = download.videoId;
    
    try {
      // Look for files with the same base name but without .part extension
      // Also search by video ID if available
      const files = readdirSync(dir);
      let completeFile = files.find(f => {
        const fBase = path.basename(f, path.extname(f));
        return fBase === baseName && 
               !f.endsWith('.part') && 
               !f.endsWith('.ytdl') &&
               f !== path.basename(filePath);
      });
      
      // If not found by base name, try searching by video ID
      if (!completeFile && videoId) {
        completeFile = files.find(f => {
          const fBase = path.basename(f, path.extname(f));
          return fBase === videoId && 
                 !f.endsWith('.part') && 
                 !f.endsWith('.ytdl');
        });
      }
      
      // If still not found, look for any file starting with video ID or base name
      if (!completeFile) {
        const searchPrefix = videoId || baseName;
        completeFile = files.find(f => {
          return f.startsWith(searchPrefix) && 
                 !f.endsWith('.part') && 
                 !f.endsWith('.ytdl') &&
                 f !== path.basename(filePath);
        });
      }
      
      if (completeFile) {
        const newPath = path.join(dir, completeFile);
        console.log(`✅ Found complete file: ${newPath}, updating database...`);
        filePath = newPath;
        
        // Update the database with the correct path
        const stats = statSync(filePath);
        await DownloadService.updateDownloadStatus(downloadId, "COMPLETED", {
          filePath: filePath,
          fileSize: stats.size,
        });
      } else {
        console.error(`❌ Could not find complete file in ${dir}. Available files:`, files);
        throw new Response("Download incomplete - only .part file found. The download may have been interrupted.", { status: 503 });
      }
    } catch (error) {
      if (error instanceof Response) throw error;
      console.error(`Error searching for complete file:`, error);
      throw new Response("Download incomplete - file is still being processed", { status: 503 });
    }
  }

  // Check if file exists
  if (!existsSync(filePath)) {
    throw new Response("File not found on server", { status: 404 });
  }

  try {
    // Get file stats for Content-Length header
    const stats = statSync(filePath);
    const fileSize = stats.size;
    
    // Additional safety: Check if the actual file on disk is a .part file
    // (in case the path in DB is wrong or file was renamed)
    const actualFileName = path.basename(filePath);
    if (actualFileName.endsWith('.part') || actualFileName.endsWith('.ytdl')) {
      console.error(`⚠️ Attempted to serve .part file for download ${downloadId}: ${filePath}`);
      throw new Response("Download incomplete - file is still being processed", { status: 503 });
    }
    
    // Additional safety: Verify file size matches what's in database (if available)
    if (download.fileSize && fileSize !== download.fileSize) {
      console.warn(`File size mismatch for download ${downloadId}: DB=${download.fileSize}, FS=${fileSize}`);
    }
    
    const fileName = download.title
      ? `${download.title.replace(/[^a-z0-9]/gi, "_")}.${path.extname(filePath).slice(1)}`
      : `video_${download.videoId || downloadId}.${path.extname(filePath).slice(1)}`;

    // Check for Range header for partial content support
    const range = request.headers.get("range");
    
    if (range) {
      // Parse range header
      const parts = range.replace(/bytes=/, "").split("-");
      const start = parseInt(parts[0], 10);
      const end = parts[1] ? parseInt(parts[1], 10) : fileSize - 1;
      const chunksize = end - start + 1;
      
      // Create read stream for the requested range
      const nodeStream = createReadStream(filePath, { start, end });
      const webStream = Readable.toWeb(nodeStream);
      
      return new Response(webStream, {
        status: 206, // Partial Content
        headers: {
          "Content-Range": `bytes ${start}-${end}/${fileSize}`,
          "Accept-Ranges": "bytes",
          "Content-Length": chunksize.toString(),
          "Content-Type": "video/mp4",
          "Content-Disposition": `attachment; filename="${fileName}"`,
        },
      });
    } else {
      // Stream the entire file
      const nodeStream = createReadStream(filePath);
      const webStream = Readable.toWeb(nodeStream);
      
      return new Response(webStream, {
        headers: {
          "Content-Type": "video/mp4",
          "Content-Disposition": `attachment; filename="${fileName}"`,
          "Content-Length": fileSize.toString(),
          "Accept-Ranges": "bytes",
        },
      });
    }
  } catch (error) {
    console.error(`Error serving file for download ID ${downloadId}:`, error);
    throw new Response("Error reading file", { status: 500 });
  }
}

