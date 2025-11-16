-- CreateTable
CREATE TABLE "downloads" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "url" TEXT NOT NULL,
    "title" TEXT,
    "status" TEXT NOT NULL DEFAULT 'PENDING',
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "started_at" DATETIME,
    "completed_at" DATETIME,
    "file_path" TEXT,
    "file_size" INTEGER,
    "error_message" TEXT,
    "video_id" TEXT,
    "is_live" BOOLEAN NOT NULL DEFAULT false,
    "is_scheduled" BOOLEAN NOT NULL DEFAULT false,
    "scheduled_start_time" DATETIME,
    "start_time" INTEGER,
    "end_time" INTEGER
);

-- CreateTable
CREATE TABLE "queue" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "download_id" INTEGER NOT NULL,
    "priority" INTEGER NOT NULL DEFAULT 0,
    "created_at" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "queue_download_id_fkey" FOREIGN KEY ("download_id") REFERENCES "downloads" ("id") ON DELETE CASCADE ON UPDATE CASCADE
);

-- CreateIndex
CREATE INDEX "downloads_status_idx" ON "downloads"("status");

-- CreateIndex
CREATE INDEX "downloads_video_id_idx" ON "downloads"("video_id");

-- CreateIndex
CREATE INDEX "downloads_created_at_idx" ON "downloads"("created_at");

-- CreateIndex
CREATE UNIQUE INDEX "queue_download_id_key" ON "queue"("download_id");

-- CreateIndex
CREATE INDEX "queue_priority_created_at_idx" ON "queue"("priority", "created_at");
