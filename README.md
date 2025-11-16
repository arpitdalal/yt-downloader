# YouTube to OneDrive Downloader

A full-stack web application that allows users to download YouTube videos and automatically upload them to OneDrive. Built with React Router v7, Prisma ORM, and Python yt-dlp.

## Features

- 🎥 **YouTube Video Download**: Download videos, live streams, and scheduled content
- 📁 **OneDrive Integration**: Automatic upload to OneDrive folder
- 🔄 **Queue Management**: Handle multiple concurrent downloads
- 📊 **Real-time Status**: Track download progress and queue position
- 🎯 **Duplicate Detection**: Avoid re-downloading existing videos
- 📱 **Responsive UI**: Modern, mobile-friendly interface
- 🚀 **Cost-effective**: Optimized for Fly.io free tier

## Tech Stack

- **Frontend**: React Router v7, TypeScript, Tailwind CSS
- **Backend**: Node.js, Prisma ORM, SQLite
- **Download Engine**: Python, yt-dlp
- **Deployment**: Fly.io, Docker
- **Package Manager**: pnpm

## Prerequisites

- Node.js 20+
- Python 3.11+
- pnpm
- Fly.io CLI (for deployment)

## Local Development Setup

1. **Clone and install dependencies**:
   ```bash
   git clone <repository-url>
   cd yt-downloader
   pnpm install
   ```

2. **Install Python dependencies**:
   ```bash
   pnpm python:install
   ```

3. **Set up the database**:
   ```bash
   # Generate Prisma client
   pnpm db:generate
   
   # Push schema to database
   pnpm db:push
   
   # Seed with sample data (optional)
   pnpm db:seed
   ```

4. **Start the development server**:
   ```bash
   pnpm dev
   ```

5. **Open your browser**:
   Navigate to `http://localhost:3000`

## Environment Variables

Create a `.env` file in the root directory:

```env
DATABASE_URL="file:./data/downloads.db"
NODE_ENV="development"
MAX_CONCURRENT_DOWNLOADS="2"
```

## Usage

1. **Add a YouTube URL**: Enter a valid YouTube URL in the input field
2. **Configure download options**: 
   - For live streams, choose whether to download from start or current point
   - For scheduled videos, the app will wait until the stream starts
3. **Monitor progress**: Track download status and queue position
4. **Access files**: Completed downloads are automatically uploaded to OneDrive

## Project Structure

```
yt-downloader/
├── app/
│   ├── lib/                 # Shared utilities
│   │   ├── db.ts           # Prisma database client
│   │   ├── types.ts        # TypeScript type definitions
│   │   ├── download-service.ts # Database operations
│   │   └── worker.ts       # Background download processing
│   ├── routes/             # React Router routes
│   │   ├── _index.tsx      # Main home page
│   │   ├── api.validate.ts # URL validation API
│   │   └── api.status.ts   # Queue status API
│   └── root.tsx            # Root component
├── python/
│   ├── downloader.py       # YouTube downloader (yt-dlp)
│   └── requirements.txt    # Python dependencies
├── prisma/
│   └── schema.prisma       # Database schema
├── scripts/
│   └── seed.ts             # Database seeding
├── data/                   # SQLite database (created automatically)
├── fly.toml               # Fly.io configuration
└── Dockerfile             # Docker configuration
```

## Database Schema

### Downloads Table
- `id`: Primary key
- `url`: YouTube URL
- `title`: Video title
- `status`: Download status (PENDING, DOWNLOADING, COMPLETED, FAILED)
- `videoId`: YouTube video ID (unique)
- `isLive`: Whether the video is live
- `isScheduled`: Whether the video is scheduled
- `filePath`: Local file path where video is stored
- `fileSize`: File size in bytes
- `errorMessage`: Error message if failed
- `startTime`: Start time in seconds for video cutting (optional)
- `endTime`: End time in seconds for video cutting (optional)

### Queue Table
- `id`: Primary key
- `downloadId`: Foreign key to downloads
- `priority`: Queue priority
- `createdAt`: Queue entry timestamp

## Deployment to Fly.io

1. **Install Fly.io CLI**:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **Login to Fly.io**:
   ```bash
   fly auth login
   ```

3. **Create the app**:
   ```bash
   fly apps create yt-downloader
   ```

4. **Create persistent volume**:
   ```bash
   fly volumes create downloads_data --size 3
   ```

5. **Deploy**:
   ```bash
   fly deploy
   ```

6. **Open the app**:
   ```bash
   fly open
   ```

## Configuration

### Fly.io Resources (Free Tier)
- **CPU**: 0.5 vCPU shared
- **Memory**: 256MB RAM
- **Storage**: 3GB persistent volume
- **Bandwidth**: 160GB/month

### Concurrent Downloads
The app is configured to handle 2 concurrent downloads by default. This can be adjusted by modifying:
- `MAX_CONCURRENT_DOWNLOADS` environment variable
- `MAX_CONCURRENT_DOWNLOADS` constant in `app/lib/worker.ts`

## OneDrive Integration

Currently, the app includes a placeholder for OneDrive integration. To implement full OneDrive support:

1. **Set up Microsoft Graph API**:
   - Register an application in Azure AD
   - Get client ID and client secret
   - Configure permissions for OneDrive

2. **Implement upload function**:
   - Replace the placeholder in `app/lib/worker.ts`
   - Use Microsoft Graph API to upload files
   - Generate sharing links

## Monitoring and Logs

### View logs in Fly.io:
```bash
fly logs
```

### Monitor queue status:
The app provides real-time queue status through the web interface and API endpoints.

## Troubleshooting

### Common Issues

1. **Python dependencies not found**:
   ```bash
   pnpm python:install
   ```

2. **Database connection errors**:
   ```bash
   pnpm db:generate
   pnpm db:push
   ```

3. **Download failures**:
   - Check if yt-dlp is up to date
   - Verify YouTube URL is accessible
   - Check available disk space

4. **Queue not processing**:
   - Restart the application
   - Check worker logs
   - Verify database connectivity

### Performance Optimization

- **Memory usage**: Monitor with `fly status`
- **Storage cleanup**: Temporary files are automatically cleaned up
- **Queue management**: Failed downloads are retried automatically

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review Fly.io logs
3. Open an issue on GitHub

---

**Note**: This application is designed for internal use. Ensure compliance with YouTube's Terms of Service and OneDrive usage policies.
