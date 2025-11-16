import { prisma } from "../app/lib/db.js";

async function main() {
  // Create some sample downloads for testing
  const sampleDownloads = [
    {
      url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      title: "Rick Astley - Never Gonna Give You Up",
      videoId: "dQw4w9WgXcQ",
      status: "COMPLETED" as const,
      filePath: "/tmp/dQw4w9WgXcQ.mp4",
      fileSize: 1024000, // 1MB
      isLive: false,
      isScheduled: false,
    },
    {
      url: "https://www.youtube.com/watch?v=9bZkp7q19f0",
      title: "PSY - GANGNAM STYLE",
      videoId: "9bZkp7q19f0",
      status: "PENDING" as const,
      isLive: false,
      isScheduled: false,
    },
  ];

  for (const downloadData of sampleDownloads) {
    const download = await prisma.download.create({
      data: downloadData,
    });

    if (download.status === "PENDING") {
      await prisma.queueItem.create({
        data: {
          downloadId: download.id,
          priority: 0,
        },
      });
    }
  }
}

main()
  .catch((e) => {
    console.error("❌ Error seeding database:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
