// AutoClip Studio - Upgraded Frontend with Custom Delete Modal & Robust Replacement

let currentProjectId = null;
let currentProjectData = null;
let selectedFile = null;
let targetClipForReplace = null;
let replacementFile = null;
let viewMode = window.innerWidth <= 640 ? 'list' : 'list';
let progressPollInterval = null;
let projectToDeleteId = null;

// DOM Elements
const navProjectsBtn = document.getElementById('navProjectsBtn');
const navNewProjectBtn = document.getElementById('navNewProjectBtn');
const projectsCountBadge = document.getElementById('projectsCountBadge');

const projectsView = document.getElementById('projectsView');
const uploadView = document.getElementById('uploadView');
const studioView = document.getElementById('studioView');

const projectsListContainer = document.getElementById('projectsListContainer');
const noProjectsNotice = document.getElementById('noProjectsNotice');

const dropzone = document.getElementById('dropzone');
const videoFileInput = document.getElementById('videoFileInput');
const selectedFileInfo = document.getElementById('selectedFileInfo');
const selectedFileName = document.getElementById('selectedFileName');
const selectedFileSize = document.getElementById('selectedFileSize');
const removeFileBtn = document.getElementById('removeFileBtn');
const projectNameInput = document.getElementById('projectNameInput');
const segmentLengthInput = document.getElementById('segmentLengthInput');
const startProcessBtn = document.getElementById('startProcessBtn');

// Studio UI
const liveSlicingBanner = document.getElementById('liveSlicingBanner');
const liveSlicingStatusText = document.getElementById('liveSlicingStatusText');
const liveSlicingCountBadge = document.getElementById('liveSlicingCountBadge');
const liveSlicingProgressBar = document.getElementById('liveSlicingProgressBar');

const studioProjectTitle = document.getElementById('studioProjectTitle');
const editProjectNameBtn = document.getElementById('editProjectNameBtn');
const studioFilename = document.getElementById('studioFilename');
const studioTotalDuration = document.getElementById('studioTotalDuration');
const studioClipCount = document.getElementById('studioClipCount');
const studioDubbedCountBadge = document.getElementById('studioDubbedCountBadge');
const dubbingProgressBar = document.getElementById('dubbingProgressBar');
const dubbingProgressPercentText = document.getElementById('dubbingProgressPercentText');

const downloadZipBtn = document.getElementById('downloadZipBtn');
const exportMergedBtn = document.getElementById('exportMergedBtn');
const deleteProjectBtn = document.getElementById('deleteProjectBtn');

const mobileZipBtn = document.getElementById('mobileZipBtn');
const mobileMergeBtn = document.getElementById('mobileMergeBtn');
const mobileActionBar = document.getElementById('mobileActionBar');

const viewModeListBtn = document.getElementById('viewModeListBtn');
const viewModeGridBtn = document.getElementById('viewModeGridBtn');
const clipsContainer = document.getElementById('clipsContainer');

// Custom Delete Modal
const customDeleteModal = document.getElementById('customDeleteModal');
const deleteModalProjectName = document.getElementById('deleteModalProjectName');
const cancelDeleteBtn = document.getElementById('cancelDeleteBtn');
const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');

// Replace Modal
const replaceModal = document.getElementById('replaceModal');
const closeReplaceModal = document.getElementById('closeReplaceModal');
const cancelReplaceBtn = document.getElementById('cancelReplaceBtn');
const confirmReplaceBtn = document.getElementById('confirmReplaceBtn');
const repFileInput = document.getElementById('repFileInput');
const repDropzone = document.getElementById('repDropzone');
const repDropText = document.getElementById('repDropText');
const replaceTargetTime = document.getElementById('replaceTargetTime');
const replaceModalSubtitle = document.getElementById('replaceModalSubtitle');
const repProgress = document.getElementById('repProgress');

// Player Modal
const playerModal = document.getElementById('playerModal');
const closePlayerModal = document.getElementById('closePlayerModal');
const modalVideoPlayer = document.getElementById('modalVideoPlayer');
const playerModalDetails = document.getElementById('playerModalDetails');
const playerModalDownloadBtn = document.getElementById('playerModalDownloadBtn');

function updateIcons() {
  if (window.lucide) {
    lucide.createIcons();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  setupEventListeners();
  loadProjectsList(true);

  // Keep-alive heartbeat every 4 minutes to prevent cloud sleeping
  setInterval(() => {
    fetch('/api/ping').catch(() => {});
  }, 240000);
});

function formatBytes(bytes, decimals = 1) {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function setDuration(seconds) {
  segmentLengthInput.value = seconds;
}

function hideAllViews() {
  projectsView.classList.add('hidden');
  uploadView.classList.add('hidden');
  studioView.classList.add('hidden');
  if (mobileActionBar) mobileActionBar.classList.add('hidden');
}

function showProjectsView() {
  stopProgressPolling();
  hideAllViews();
  projectsView.classList.remove('hidden');
  loadProjectsList();
}

function showUploadView() {
  stopProgressPolling();
  hideAllViews();
  uploadView.classList.remove('hidden');
  updateIcons();
}

function showStudioView() {
  hideAllViews();
  studioView.classList.remove('hidden');
  if (mobileActionBar && window.innerWidth <= 640) {
    mobileActionBar.classList.remove('hidden');
  }
  updateIcons();
}

function stopProgressPolling() {
  if (progressPollInterval) {
    clearInterval(progressPollInterval);
    progressPollInterval = null;
  }
}

function setupEventListeners() {
  navProjectsBtn.addEventListener('click', showProjectsView);
  navNewProjectBtn.addEventListener('click', showUploadView);

  dropzone.addEventListener('click', () => videoFileInput.click());
  videoFileInput.addEventListener('change', (e) => handleFileSelected(e.target.files[0]));

  ['dragenter', 'dragover'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.add('border-indigo-500', 'bg-indigo-950/30');
    });
  });

  ['dragleave', 'drop'].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      dropzone.classList.remove('border-indigo-500', 'bg-indigo-950/30');
    });
  });

  dropzone.addEventListener('drop', (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelected(e.dataTransfer.files[0]);
    }
  });

  removeFileBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    resetFileInput();
  });

  startProcessBtn.addEventListener('click', startUploadAndLiveSlicing);

  viewModeListBtn.addEventListener('click', () => setViewMode('list'));
  viewModeGridBtn.addEventListener('click', () => setViewMode('grid'));

  downloadZipBtn.addEventListener('click', downloadZip);
  mobileZipBtn.addEventListener('click', downloadZip);
  exportMergedBtn.addEventListener('click', exportMerged);
  mobileMergeBtn.addEventListener('click', exportMerged);

  // Custom Delete Modal Trigger
  deleteProjectBtn.addEventListener('click', () => {
    if (currentProjectId && currentProjectData) {
      openDeleteModal(currentProjectId, currentProjectData.project_name);
    }
  });

  cancelDeleteBtn.addEventListener('click', closeDeleteModal);
  confirmDeleteBtn.addEventListener('click', executeProjectDeletion);

  editProjectNameBtn.addEventListener('click', handleRenameProject);

  closeReplaceModal.addEventListener('click', () => replaceModal.classList.add('hidden'));
  cancelReplaceBtn.addEventListener('click', () => replaceModal.classList.add('hidden'));
  repDropzone.addEventListener('click', () => repFileInput.click());
  repFileInput.addEventListener('change', (e) => handleReplacementFileSelected(e.target.files[0]));
  confirmReplaceBtn.addEventListener('click', submitClipReplacement);

  closePlayerModal.addEventListener('click', () => {
    modalVideoPlayer.pause();
    modalVideoPlayer.src = '';
    playerModal.classList.add('hidden');
  });
}

function openDeleteModal(projectId, projectName) {
  projectToDeleteId = projectId;
  deleteModalProjectName.textContent = projectName || `Project #${projectId}`;
  customDeleteModal.classList.remove('hidden');
  updateIcons();
}

function closeDeleteModal() {
  projectToDeleteId = null;
  customDeleteModal.classList.add('hidden');
}

async function executeProjectDeletion() {
  if (!projectToDeleteId) return;

  confirmDeleteBtn.disabled = true;
  confirmDeleteBtn.innerHTML = `<i data-lucide="loader-2" class="w-3.5 h-3.5 animate-spin mr-1"></i> Deleting...`;
  updateIcons();

  try {
    const res = await fetch(`/api/project/${projectToDeleteId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Failed to delete');

    closeDeleteModal();
    if (currentProjectId === projectToDeleteId) {
      currentProjectId = null;
      currentProjectData = null;
      showProjectsView();
    } else {
      loadProjectsList();
    }
  } catch (err) {
    alert('Delete error: ' + err.message);
  } finally {
    confirmDeleteBtn.disabled = false;
    confirmDeleteBtn.innerHTML = 'Yes, Delete';
  }
}

function setViewMode(mode) {
  viewMode = mode;
  if (mode === 'list') {
    viewModeListBtn.className = 'px-2.5 py-1 text-xs rounded-md bg-indigo-600 text-white font-medium flex items-center gap-1';
    viewModeGridBtn.className = 'px-2.5 py-1 text-xs rounded-md text-slate-400 hover:text-white font-medium flex items-center gap-1';
  } else {
    viewModeGridBtn.className = 'px-2.5 py-1 text-xs rounded-md bg-indigo-600 text-white font-medium flex items-center gap-1';
    viewModeListBtn.className = 'px-2.5 py-1 text-xs rounded-md text-slate-400 hover:text-white font-medium flex items-center gap-1';
  }
  if (currentProjectData) {
    renderClips(currentProjectData);
  }
}

async function loadProjectsList(autoSelectFirstIfAvailable = false) {
  try {
    const res = await fetch(`/api/projects?t=${Date.now()}`);
    if (!res.ok) return;
    const projects = await res.json();

    projectsCountBadge.textContent = projects.length;

    if (projects.length === 0) {
      projectsListContainer.innerHTML = '';
      noProjectsNotice.classList.remove('hidden');
      if (autoSelectFirstIfAvailable) {
        showUploadView();
      }
      return;
    }

    noProjectsNotice.classList.add('hidden');
    projectsListContainer.innerHTML = '';

    projects.forEach(p => {
      const card = document.createElement('div');
      card.className = 'bg-slate-900/80 border border-slate-800 rounded-xl p-4 project-card flex flex-col justify-between cursor-pointer hover:bg-slate-900';
      
      const thumbUrl = p.cover_thumb ? `/api/media/${p.project_id}/${p.cover_thumb}?t=${Date.now()}` : '/static/thumb_fallback.jpg';
      const percentReplaced = p.total_clips > 0 ? Math.round((p.replaced_count / p.total_clips) * 100) : 0;
      
      card.innerHTML = `
        <div>
          <div class="relative aspect-video rounded-lg overflow-hidden bg-black mb-3 border border-slate-800/80">
            <img src="${thumbUrl}" alt="Project cover" class="w-full h-full object-cover" onerror="this.src='/static/thumb_fallback.jpg'">
            <div class="absolute bottom-1.5 right-1.5 px-2 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white">
              ${p.duration_formatted}
            </div>
            ${p.status === 'processing' ? `
              <div class="absolute inset-0 bg-indigo-950/80 backdrop-blur-xs flex items-center justify-center text-xs font-semibold text-indigo-200">
                <i data-lucide="loader-2" class="w-4 h-4 animate-spin mr-1.5"></i> Live Slicing (${p.ready_count || 0}/${p.total_clips || '?'})
              </div>` : ''}
          </div>

          <h3 class="font-bold text-white text-sm truncate mb-1">${p.project_name}</h3>
          <p class="text-[11px] text-slate-400 truncate mb-2.5">${p.original_filename}</p>
        </div>

        <div>
          <div class="flex items-center justify-between text-xs text-slate-400 mb-1.5">
            <span>${p.total_clips} Clips (${p.ready_count || p.total_clips} Ready)</span>
            <span class="text-emerald-400 font-medium">${p.replaced_count}/${p.total_clips} Dubbed</span>
          </div>

          <div class="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden border border-slate-800 mb-3">
            <div class="bg-emerald-500 h-full rounded-full" style="width: ${percentReplaced}%"></div>
          </div>

          <div class="flex items-center gap-2">
            <button class="flex-1 py-1.5 px-3 rounded-lg bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-semibold transition" onclick="openProject('${p.project_id}')">
              Open Workspace
            </button>
            <button class="p-1.5 rounded-lg bg-slate-800 hover:bg-red-600/30 text-slate-400 hover:text-red-300 border border-slate-700 transition" title="Delete Project" onclick="triggerDeleteFromList(event, '${p.project_id}', '${p.project_name.replace(/'/g, "\\'")}')">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `;

      projectsListContainer.appendChild(card);
    });

    updateIcons();
  } catch (e) {
    console.error("Error loading projects:", e);
  }
}

function triggerDeleteFromList(e, projectId, projectName) {
  e.stopPropagation();
  openDeleteModal(projectId, projectName);
}

async function openProject(projectId) {
  try {
    stopProgressPolling();
    const res = await fetch(`/api/project/${projectId}?t=${Date.now()}`);
    if (!res.ok) throw new Error("Project not found");
    const project = await res.json();
    currentProjectId = projectId;
    currentProjectData = project;
    renderStudioProject(project);
    showStudioView();

    if (project.status === 'processing') {
      startLivePolling(projectId);
    } else {
      liveSlicingBanner.classList.add('hidden');
    }
  } catch (err) {
    alert("Could not load project: " + err.message);
  }
}

function handleFileSelected(file) {
  if (!file) return;
  selectedFile = file;
  selectedFileName.textContent = file.name;
  selectedFileSize.textContent = formatBytes(file.size);
  selectedFileInfo.classList.remove('hidden');
  startProcessBtn.disabled = false;
  if (!projectNameInput.value) {
    projectNameInput.value = file.name.replace(/\.[^/.]+$/, "");
  }
  updateIcons();
}

function resetFileInput() {
  selectedFile = null;
  videoFileInput.value = '';
  selectedFileInfo.classList.add('hidden');
  startProcessBtn.disabled = true;
}

async function startUploadAndLiveSlicing() {
  if (!selectedFile) return;

  const segmentLength = parseFloat(segmentLengthInput.value) || 60.0;
  const pName = projectNameInput.value.trim() || selectedFile.name;

  const formData = new FormData();
  formData.append('file', selectedFile);
  formData.append('segment_length', segmentLength);
  formData.append('project_name', pName);

  startProcessBtn.disabled = true;
  startProcessBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Uploading & Starting Live Slicer...</span>`;
  updateIcons();

  try {
    const res = await fetch('/api/upload', {
      method: 'POST',
      body: formData
    });

    if (!res.ok) throw new Error(`Upload failed: ${res.statusText}`);

    const data = await res.json();
    currentProjectId = data.project_id;
    
    showStudioView();
    startLivePolling(currentProjectId);
    resetFileInput();
  } catch (err) {
    alert('Upload error: ' + err.message);
  } finally {
    startProcessBtn.disabled = false;
    startProcessBtn.innerHTML = `<i data-lucide="scissors" class="w-4 h-4"></i><span>Start Live Slicing</span>`;
    updateIcons();
  }
}

function startLivePolling(projectId) {
  stopProgressPolling();
  liveSlicingBanner.classList.remove('hidden');

  progressPollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${projectId}?t=${Date.now()}`);
      if (!res.ok) return;

      const progressData = await res.json();
      
      if (progressData.project) {
        currentProjectData = progressData.project;
        renderStudioProject(progressData.project);
      }

      if (progressData.status === 'processing') {
        const percent = progressData.percent || 10;
        liveSlicingProgressBar.style.width = `${percent}%`;
        liveSlicingStatusText.textContent = progressData.message || `Live Slicing: ${progressData.current} of ${progressData.total} Ready`;
        liveSlicingCountBadge.textContent = `${progressData.current} / ${progressData.total} Ready`;
      } else if (progressData.status === 'completed' || progressData.status === 'ready') {
        stopProgressPolling();
        liveSlicingBanner.classList.add('hidden');
      }
    } catch (e) {
      console.error("Live polling error:", e);
    }
  }, 1200);
}

function renderStudioProject(project) {
  currentProjectData = project;
  currentProjectId = project.project_id;

  studioProjectTitle.textContent = project.project_name || `Project #${project.project_id}`;
  studioFilename.textContent = project.original_filename || 'video.mp4';
  studioTotalDuration.textContent = `Duration: ${project.original_info?.duration_formatted || '--:--'}`;
  
  const readyClips = project.clips.filter(c => c.status === 'ready');
  const replacedClips = project.clips.filter(c => c.is_replaced);

  studioClipCount.textContent = `Total Clips: ${project.clips.length} (${readyClips.length} Ready)`;
  studioDubbedCountBadge.textContent = `${replacedClips.length} Dubbed`;

  const percentDubbed = project.clips.length > 0 ? Math.round((replacedClips.length / project.clips.length) * 100) : 0;
  dubbingProgressBar.style.width = `${percentDubbed}%`;
  dubbingProgressPercentText.textContent = `${percentDubbed}% (${replacedClips.length} / ${project.clips.length} Clips Replaced)`;

  renderClips(project);
}

function renderClips(project) {
  clipsContainer.innerHTML = '';

  if (viewMode === 'grid') {
    clipsContainer.className = 'grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4';
  } else {
    clipsContainer.className = 'space-y-2';
  }

  project.clips.forEach(clip => {
    const isReady = clip.status === 'ready';
    const isProcessing = clip.status === 'processing';
    const isPending = !isReady && !isProcessing;

    const cacheBust = Date.now();
    const thumbUrl = isReady ? `/api/media/${project.project_id}/${clip.thumb_filename}?t=${cacheBust}` : '/static/thumb_fallback.jpg';
    const downloadUrl = `/api/download/clip/${project.project_id}/${clip.clip_id}`;

    let statusBadge = '';
    if (clip.is_replaced) {
      statusBadge = `<span class="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[10px] font-semibold flex items-center gap-1">
        <i data-lucide="check-circle" class="w-3 h-3"></i> Dubbed
      </span>`;
    } else if (clip.is_remainder && isReady) {
      statusBadge = `<span class="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-semibold flex items-center gap-1">
        <i data-lucide="star" class="w-3 h-3"></i> Tail Clip
      </span>`;
    } else if (isProcessing) {
      statusBadge = `<span class="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 text-[10px] font-semibold flex items-center gap-1 animate-pulse">
        <i data-lucide="loader-2" class="w-3 h-3 animate-spin"></i> Slicing now...
      </span>`;
    } else if (isPending) {
      statusBadge = `<span class="px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700 text-[10px] font-medium flex items-center gap-1">
        <i data-lucide="clock" class="w-3 h-3"></i> In Queue
      </span>`;
    }

    if (viewMode === 'list') {
      const row = document.createElement('div');
      row.className = `bg-slate-900/80 border ${clip.is_replaced ? 'border-emerald-500/40 bg-emerald-950/10' : isProcessing ? 'border-indigo-500/60 ring-1 ring-indigo-500/20' : 'border-slate-800/90'} rounded-xl p-2.5 sm:p-3 flex items-center justify-between gap-3 clip-list-item ${!isReady ? 'opacity-85' : ''}`;
      
      row.innerHTML = `
        <div class="flex items-center gap-3 min-w-0">
          <div class="relative w-20 sm:w-24 aspect-video rounded-lg overflow-hidden bg-black flex-shrink-0 ${isReady ? 'cursor-pointer group' : ''}" onclick="${isReady ? `openPlayerModal('${project.project_id}', '${clip.clip_id}', '${clip.filename}', '${clip.title}', '${clip.start_formatted} - ${clip.end_formatted}')` : ''}">
            <img src="${thumbUrl}" class="w-full h-full object-cover ${isReady ? 'group-hover:scale-105' : 'opacity-40'} transition-transform" onerror="this.src='/static/thumb_fallback.jpg'">
            
            ${isReady ? `
              <div class="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                <i data-lucide="play" class="w-4 h-4 text-white"></i>
              </div>
            ` : isProcessing ? `
              <div class="absolute inset-0 bg-indigo-950/70 flex items-center justify-center">
                <i data-lucide="loader-2" class="w-4 h-4 text-indigo-400 animate-spin"></i>
              </div>
            ` : `
              <div class="absolute inset-0 bg-black/60 flex items-center justify-center">
                <i data-lucide="clock" class="w-4 h-4 text-slate-500"></i>
              </div>
            `}

            <div class="absolute bottom-1 right-1 px-1 py-0.2 rounded bg-black/80 text-[9px] font-mono text-white">
              ${clip.duration_formatted}
            </div>
          </div>

          <div class="min-w-0">
            <div class="flex items-center gap-2 mb-0.5">
              <h4 class="font-bold text-white text-xs sm:text-sm truncate">Clip ${String(clip.index).padStart(2, '0')}</h4>
              ${statusBadge}
            </div>
            <div class="text-[11px] text-slate-400 font-mono flex items-center gap-2">
              <span>${clip.start_formatted} - ${clip.end_formatted}</span>
              ${isReady ? `<span class="text-slate-500 hidden xs:inline">• ${formatBytes(clip.filesize)}</span>` : ''}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-1.5 flex-shrink-0">
          ${isReady ? `
            <a href="${downloadUrl}" class="p-2 sm:px-3 sm:py-1.5 rounded-lg bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-semibold transition flex items-center gap-1" title="Download Clip">
              <i data-lucide="download" class="w-3.5 h-3.5"></i>
              <span class="hidden sm:inline">Download</span>
            </a>

            <button onclick="openReplaceModal('${clip.clip_id}', '${clip.title}', '${clip.start_formatted} - ${clip.end_formatted} (${clip.duration_formatted})')" class="p-2 sm:px-3 sm:py-1.5 rounded-lg ${clip.is_replaced ? 'bg-emerald-600/20 text-emerald-300 border-emerald-500/40 hover:bg-emerald-600 hover:text-white' : 'bg-slate-800 text-slate-300 hover:bg-purple-600/30 hover:text-purple-200 border-slate-700 hover:border-purple-500/40'} border text-xs font-semibold transition flex items-center gap-1" title="Replace with Dubbed Clip">
              <i data-lucide="repeat" class="w-3.5 h-3.5 ${clip.is_replaced ? 'text-emerald-400' : 'text-purple-400'}"></i>
              <span class="hidden sm:inline">${clip.is_replaced ? 'Re-dub' : 'Replace'}</span>
            </button>
          ` : isProcessing ? `
            <span class="text-[11px] font-mono text-indigo-400 px-3 py-1 rounded-lg bg-indigo-950/60 border border-indigo-500/30 flex items-center gap-1.5">
              <i data-lucide="scissors" class="w-3 h-3 animate-pulse"></i> Slicing...
            </span>
          ` : `
            <span class="text-[11px] font-mono text-slate-500 px-3 py-1 rounded-lg bg-slate-950 border border-slate-800">
              Queued
            </span>
          `}
        </div>
      `;

      clipsContainer.appendChild(row);
    } else {
      const card = document.createElement('div');
      card.className = `bg-slate-900/80 border ${clip.is_replaced ? 'border-emerald-500/40' : isProcessing ? 'border-indigo-500/60' : 'border-slate-800'} rounded-xl overflow-hidden flex flex-col clip-card`;

      card.innerHTML = `
        <div class="relative aspect-video-thumb bg-black overflow-hidden ${isReady ? 'cursor-pointer group' : ''}" onclick="${isReady ? `openPlayerModal('${project.project_id}', '${clip.clip_id}', '${clip.filename}', '${clip.title}', '${clip.start_formatted} - ${clip.end_formatted}')` : ''}">
          <img src="${thumbUrl}" class="w-full h-full object-cover ${isReady ? 'group-hover:scale-105' : 'opacity-40'} transition-transform" onerror="this.src='/static/thumb_fallback.jpg'">
          
          ${isReady ? `
            <div class="absolute inset-0 bg-black/40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <div class="w-10 h-10 rounded-full bg-indigo-600/90 text-white flex items-center justify-center shadow-lg">
                <i data-lucide="play" class="w-4 h-4 ml-0.5"></i>
              </div>
            </div>
          ` : isProcessing ? `
            <div class="absolute inset-0 bg-indigo-950/70 flex items-center justify-center">
              <i data-lucide="loader-2" class="w-6 h-6 text-indigo-400 animate-spin"></i>
            </div>
          ` : ''}

          <div class="absolute bottom-1.5 right-1.5 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white">
            ${clip.duration_formatted}
          </div>
          <div class="absolute top-2 left-2">
            ${statusBadge}
          </div>
        </div>

        <div class="p-3.5 flex-1 flex flex-col justify-between">
          <div>
            <div class="flex items-center justify-between mb-1">
              <h4 class="font-bold text-white text-xs sm:text-sm">Clip ${String(clip.index).padStart(2, '0')}</h4>
              <span class="text-[11px] font-mono text-slate-400 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
                ${clip.start_formatted} - ${clip.end_formatted}
              </span>
            </div>
            <div class="text-[11px] text-slate-500 mb-3">
              ${isReady ? formatBytes(clip.filesize) : isProcessing ? 'Generating clip file...' : 'Waiting in queue...'}
            </div>
          </div>

          <div class="flex items-center gap-1.5 pt-2 border-t border-slate-800/80">
            ${isReady ? `
              <a href="${downloadUrl}" class="flex-1 py-1.5 px-2 rounded-lg bg-indigo-600/20 hover:bg-indigo-600 text-indigo-300 hover:text-white border border-indigo-500/30 text-xs font-semibold transition flex items-center justify-center gap-1">
                <i data-lucide="download" class="w-3.5 h-3.5"></i>
                <span>Download</span>
              </a>
              <button onclick="openReplaceModal('${clip.clip_id}', '${clip.title}', '${clip.start_formatted} - ${clip.end_formatted} (${clip.duration_formatted})')" class="flex-1 py-1.5 px-2 rounded-lg bg-slate-800 hover:bg-purple-600/30 text-slate-300 hover:text-purple-200 border border-slate-700 hover:border-purple-500/40 text-xs font-semibold transition flex items-center justify-center gap-1">
                <i data-lucide="repeat" class="w-3.5 h-3.5 text-purple-400"></i>
                <span>Replace</span>
              </button>
            ` : `
              <div class="w-full text-center py-1 text-xs text-slate-500 font-mono">
                ${isProcessing ? 'Slicing...' : 'Pending'}
              </div>
            `}
          </div>
        </div>
      `;

      clipsContainer.appendChild(card);
    }
  });

  updateIcons();
}

function openPlayerModal(projectId, clipId, filename, title, timerange) {
  modalVideoPlayer.src = `/api/media/${projectId}/${filename}?t=${Date.now()}`;
  playerModalDetails.textContent = `${title} • ${timerange}`;
  playerModalDownloadBtn.href = `/api/download/clip/${projectId}/${clipId}`;
  playerModal.classList.remove('hidden');
  modalVideoPlayer.play().catch(() => {});
  updateIcons();
}

function openReplaceModal(clipId, title, timeRange) {
  targetClipForReplace = clipId;
  replacementFile = null;
  repFileInput.value = '';
  repDropText.textContent = 'Select Dubbed Video File';
  confirmReplaceBtn.disabled = true;
  repProgress.classList.add('hidden');

  replaceModalSubtitle.textContent = `Upload dubbed video for ${title}`;
  replaceTargetTime.textContent = timeRange;

  replaceModal.classList.remove('hidden');
  updateIcons();
}

function handleReplacementFileSelected(file) {
  if (!file) return;
  replacementFile = file;
  repDropText.textContent = `${file.name} (${formatBytes(file.size)})`;
  confirmReplaceBtn.disabled = false;
}

async function submitClipReplacement() {
  if (!replacementFile || !targetClipForReplace || !currentProjectId) return;

  const formData = new FormData();
  formData.append('file', replacementFile);

  confirmReplaceBtn.disabled = true;
  cancelReplaceBtn.disabled = true;
  repProgress.classList.remove('hidden');

  try {
    const res = await fetch(`/api/replace/${currentProjectId}/${targetClipForReplace}`, {
      method: 'POST',
      body: formData
    });

    if (!res.ok) throw new Error(await res.text());

    const updatedProject = await res.json();
    currentProjectData = updatedProject;
    replaceModal.classList.add('hidden');
    renderStudioProject(updatedProject);
    alert('Clip replaced successfully with your dubbed video!');
  } catch (err) {
    alert('Replace failed: ' + err.message);
  } finally {
    confirmReplaceBtn.disabled = false;
    cancelReplaceBtn.disabled = false;
    repProgress.classList.add('hidden');
  }
}

function downloadZip() {
  if (!currentProjectId) return;
  window.location.href = `/api/download/zip/${currentProjectId}`;
}

async function exportMerged() {
  if (!currentProjectId) return;

  const originalHtml = exportMergedBtn.innerHTML;
  exportMergedBtn.innerHTML = `<i data-lucide="loader-2" class="w-4 h-4 animate-spin"></i><span>Merging All Clips...</span>`;
  exportMergedBtn.disabled = true;
  if (mobileMergeBtn) mobileMergeBtn.disabled = true;
  updateIcons();

  try {
    const res = await fetch(`/api/export-merged/${currentProjectId}`, {
      method: 'POST'
    });

    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();

    alert('Final video merged successfully! Download starting now.');
    window.location.href = data.download_url;
  } catch (err) {
    alert('Merge failed: ' + err.message);
  } finally {
    exportMergedBtn.innerHTML = originalHtml;
    exportMergedBtn.disabled = false;
    if (mobileMergeBtn) mobileMergeBtn.disabled = false;
    updateIcons();
  }
}

async function handleRenameProject() {
  if (!currentProjectId || !currentProjectData) return;
  const newName = prompt('Enter new project name:', currentProjectData.project_name || '');
  if (!newName || !newName.trim()) return;

  const formData = new FormData();
  formData.append('name', newName.trim());

  try {
    const res = await fetch(`/api/project/${currentProjectId}`, {
      method: 'PATCH',
      body: formData
    });
    if (!res.ok) throw new Error('Rename failed');
    const updated = await res.json();
    renderStudioProject(updated);
  } catch (err) {
    alert(err.message);
  }
}
