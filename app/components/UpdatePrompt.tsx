import type { Update } from "@tauri-apps/plugin-updater";
import { useEffect, useRef, useState } from "react";
import {
	checkForAppUpdate,
	downloadAndInstallAppUpdate,
	formatUpdateError,
	relaunchAfterUpdate,
	type UpdateDownloadProgress,
} from "../lib/updater.js";

type UpdatePhase = "available" | "downloading" | "restarting" | "error";

interface UpdatePromptProps {
	isAppBusy: boolean;
}

const INITIAL_PROGRESS: UpdateDownloadProgress = {
	downloadedBytes: 0,
	totalBytes: null,
	percent: null,
};

function formatMegabytes(bytes: number): string {
	return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

export function UpdatePrompt({ isAppBusy }: UpdatePromptProps) {
	const updateRef = useRef<Update | null>(null);
	const [phase, setPhase] = useState<UpdatePhase>("available");
	const [isVisible, setIsVisible] = useState(false);
	const [progress, setProgress] =
		useState<UpdateDownloadProgress>(INITIAL_PROGRESS);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let cancelled = false;

		void checkForAppUpdate()
			.then((update) => {
				if (cancelled || !update) {
					return;
				}
				updateRef.current = update;
				setIsVisible(true);
			})
			.catch((checkError: unknown) => {
				console.warn("Failed to check for app updates:", checkError);
			});

		return () => {
			cancelled = true;
		};
	}, []);

	if (!isVisible || !updateRef.current) {
		return null;
	}

	const update = updateRef.current;
	const isInstalling = phase === "downloading" || phase === "restarting";
	const progressLabel =
		progress.totalBytes === null
			? `${formatMegabytes(progress.downloadedBytes)} downloaded`
			: `${formatMegabytes(progress.downloadedBytes)} of ${formatMegabytes(progress.totalBytes)}`;

	const dismiss = () => {
		if (isInstalling) {
			return;
		}
		setIsVisible(false);
		updateRef.current = null;
		void update.close().catch((closeError: unknown) => {
			console.warn("Failed to release updater resource:", closeError);
		});
	};

	const install = async () => {
		if (isAppBusy || isInstalling) {
			return;
		}

		setError(null);
		setProgress(INITIAL_PROGRESS);
		setPhase("downloading");

		try {
			await downloadAndInstallAppUpdate(update, setProgress);
			setPhase("restarting");
			await relaunchAfterUpdate();
		} catch (installError) {
			setError(formatUpdateError(installError));
			setPhase("error");
		}
	};

	return (
		<aside
			className="fixed right-3 bottom-3 left-3 z-50 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-[0_18px_50px_-18px_rgba(15,23,42,0.45)] sm:right-5 sm:bottom-5 sm:left-auto sm:w-[25rem]"
			role={phase === "error" ? "alert" : "status"}
			aria-live="polite"
		>
			<div className="h-1 bg-blue-600" />
			<div className="p-4">
				<div className="flex items-start gap-3">
					<div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 ring-1 ring-blue-100">
						<svg
							aria-hidden="true"
							className="size-5"
							fill="none"
							viewBox="0 0 24 24"
							stroke="currentColor"
							strokeWidth="2"
						>
							<path
								strokeLinecap="round"
								strokeLinejoin="round"
								d="M12 3v12m0 0 4-4m-4 4-4-4M5 21h14"
							/>
						</svg>
					</div>

					<div className="min-w-0 flex-1">
						<div className="flex items-start justify-between gap-3">
							<div>
								<p className="text-sm font-semibold text-slate-900">
									{phase === "restarting"
										? "Update installed"
										: `Version ${update.version} is ready`}
								</p>
								<p className="mt-0.5 text-xs text-slate-500">
									{phase === "downloading"
										? "Downloading and verifying the update…"
										: phase === "restarting"
											? "Restarting with the new version…"
											: "A newer YouTube Downloader is available."}
								</p>
							</div>

							<button
								type="button"
								onClick={dismiss}
								disabled={isInstalling}
								className="-mt-1 -mr-1 flex size-8 shrink-0 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:invisible"
								aria-label="Dismiss update for now"
							>
								<svg
									aria-hidden="true"
									className="size-4"
									fill="none"
									viewBox="0 0 24 24"
									stroke="currentColor"
									strokeWidth="2"
								>
									<path strokeLinecap="round" d="M6 6l12 12M18 6 6 18" />
								</svg>
							</button>
						</div>

						{phase === "downloading" && (
							<div className="mt-3">
								<div
									className="h-1.5 overflow-hidden rounded-full bg-slate-100"
									role="progressbar"
									aria-label="Update download progress"
									aria-valuemin={0}
									aria-valuemax={100}
									aria-valuenow={progress.percent ?? undefined}
								>
									<div
										className={`h-full rounded-full bg-blue-600 transition-[width] duration-300 ${progress.percent === null ? "w-1/3 animate-pulse" : ""}`}
										style={
											progress.percent === null
												? undefined
												: { width: `${progress.percent}%` }
										}
									/>
								</div>
								<p className="mt-1.5 text-[11px] text-slate-500">
									{progressLabel}
								</p>
							</div>
						)}

						{error && <p className="mt-2 text-xs text-red-700">{error}</p>}

						{!isInstalling && (
							<div className="mt-3 flex items-center gap-3">
								<button
									type="button"
									onClick={() => void install()}
									disabled={isAppBusy}
									className="rounded-md bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:bg-slate-300"
								>
									{phase === "error" ? "Try again" : "Update now"}
								</button>
								{isAppBusy && (
									<p className="text-[11px] leading-4 text-slate-500">
										Finish the current download first.
									</p>
								)}
							</div>
						)}
					</div>
				</div>
			</div>
		</aside>
	);
}
