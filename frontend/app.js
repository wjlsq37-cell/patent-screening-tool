const STANDARD_FIELDS = [
  '专利名称',
  '申请号',
  '公开号',
  '申请日',
  '公开日',
  '授权日',
  '申请人',
  '发明人',
  '摘要',
  '权利要求',
  '法律状态',
  '专利类型',
  'IPC 分类号',
  '详情链接',
];

const state = {
  keywordResult: null,
  upload: null,
  columns: [],
  fieldMapping: {},
  previewExpanded: false,
  progressTimer: null,
};

const $ = (id) => document.getElementById(id);

function setStatus(id, message, type = '') {
  const el = $(id);
  el.textContent = message || '';
  el.className = `status-line ${type}`.trim();
}

function setGlobal(message, type = '') {
  const el = $('globalStatus');
  el.textContent = message || '';
  el.className = `min-h-6 text-sm ${type === 'error' ? 'text-red-700' : type === 'success' ? 'text-emerald-700' : 'text-slate-500'}`;
}

async function apiFetch(url, options = {}) {
  const response = await fetch(url, options);
  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    data = await response.json();
  }
  if (!response.ok) {
    const detail = data?.detail || data?.message || `请求失败：${response.status}`;
    throw new Error(detail);
  }
  return data;
}

function activateTab(tab) {
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.classList.toggle('active', button.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-panel').forEach((panel) => {
    panel.classList.add('hidden');
  });
  $(`tab-${tab}`).classList.remove('hidden');
  if (tab === 'history') loadHistory();
}

function renderKeywordResult(result) {
  const container = $('keywordResult');
  if (!result) {
    container.className = 'keyword-grid empty-state';
    container.textContent = '尚未生成关键词。';
    return;
  }
  container.className = 'keyword-grid';
  container.innerHTML = Object.entries(result)
    .map(([key, values]) => {
      const items = Array.isArray(values) ? values : [values];
      const content = items.length
        ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '<div class="empty-state">无</div>';
      return `<div class="keyword-card"><h3>${escapeHtml(key)}</h3>${content}</div>`;
    })
    .join('');
}

function keywordText(result) {
  if (!result) return '';
  return Object.entries(result)
    .map(([key, values]) => `${key}：\n${(Array.isArray(values) ? values : [values]).join('\n')}`)
    .join('\n\n');
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

async function loadSettings() {
  try {
    const data = await apiFetch('/api/settings');
    const ai = data.ai;
    $('apiTypeInput').value = ai.api_type || 'OpenAI-compatible';
    $('baseUrlInput').value = ai.base_url || '';
    $('modelInput').value = ai.model || '';
    $('temperatureInput').value = ai.temperature ?? 0.2;
    $('maxTokensInput').value = ai.max_tokens ?? 1800;
    $('streamInput').checked = Boolean(ai.stream);
    $('apiKeyInput').placeholder = ai.has_api_key ? '已保存 API Key，留空则不修改' : '请输入 API Key';
  } catch (error) {
    setStatus('settingsStatus', error.message, 'error');
  }
}

async function saveSettings() {
  setStatus('settingsStatus', '正在保存设置...');
  try {
    const payload = {
      api_type: $('apiTypeInput').value.trim() || 'OpenAI-compatible',
      base_url: $('baseUrlInput').value.trim(),
      api_key: $('apiKeyInput').value.trim() || null,
      model: $('modelInput').value.trim(),
      temperature: Number($('temperatureInput').value || 0.2),
      max_tokens: Number($('maxTokensInput').value || 1800),
      stream: $('streamInput').checked,
      timeout_seconds: 60,
    };
    await apiFetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    $('apiKeyInput').value = '';
    await loadSettings();
    setStatus('settingsStatus', '设置已保存。', 'success');
  } catch (error) {
    setStatus('settingsStatus', error.message, 'error');
  }
}

async function testSettings() {
  setStatus('settingsStatus', '正在测试连接...');
  try {
    const data = await apiFetch('/api/settings/test', { method: 'POST' });
    setStatus('settingsStatus', data.message || '连接成功。', 'success');
  } catch (error) {
    setStatus('settingsStatus', error.message, 'error');
  }
}

async function extractKeywords() {
  const requirement = $('requirementInput').value.trim();
  if (!requirement) {
    setStatus('keywordStatus', '请先输入专利检索需求。', 'error');
    return;
  }
  setStatus('keywordStatus', '正在调用 AI 生成关键词...');
  $('extractKeywordsBtn').disabled = true;
  try {
    const data = await apiFetch('/api/keywords/extract', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ requirement }),
    });
    state.keywordResult = data.result;
    renderKeywordResult(state.keywordResult);
    setStatus('keywordStatus', '关键词已生成，可复制到 PatentHub 检索。', 'success');
  } catch (error) {
    setStatus('keywordStatus', error.message, 'error');
  } finally {
    $('extractKeywordsBtn').disabled = false;
  }
}

async function copyKeywords() {
  const text = keywordText(state.keywordResult);
  if (!text) {
    setStatus('keywordStatus', '还没有可复制的关键词。', 'error');
    return;
  }
  await navigator.clipboard.writeText(text);
  setStatus('keywordStatus', '关键词结果已复制。', 'success');
}

async function uploadFile() {
  const file = $('fileInput').files[0];
  if (!file) {
    setStatus('uploadStatus', '请先选择 .xlsx 文件。', 'error');
    return;
  }
  const formData = new FormData();
  formData.append('file', file);
  setStatus('uploadStatus', '正在上传并读取 xlsx...');
  $('uploadBtn').disabled = true;
  try {
    const data = await apiFetch('/api/uploads', { method: 'POST', body: formData });
    applyPreview(data);
    setStatus('uploadStatus', '文件已读取，请检查预览和字段映射。', 'success');
  } catch (error) {
    setStatus('uploadStatus', error.message, 'error');
  } finally {
    $('uploadBtn').disabled = false;
  }
}

function applyPreview(data) {
  state.upload = data;
  state.columns = data.columns || [];
  state.fieldMapping = data.field_mapping || {};
  $('previewSection').classList.remove('hidden');
  state.previewExpanded = false;
  updatePreviewToggle();
  $('previewMeta').textContent = `${data.filename || ''}，共 ${data.row_count || 0} 行，预览前 ${Math.min(10, data.rows?.length || 0)} 行。`;

  const sheetSelect = $('sheetSelect');
  sheetSelect.innerHTML = (data.sheets || [])
    .map((sheet) => `<option value="${escapeHtml(sheet)}"${sheet === data.active_sheet ? ' selected' : ''}>${escapeHtml(sheet)}</option>`)
    .join('');

  renderTable('previewTable', data.rows || [], state.columns);
  renderMapping();
}

function updatePreviewToggle() {
  const content = $('previewContent');
  const button = $('togglePreviewBtn');
  content.classList.toggle('hidden', !state.previewExpanded);
  button.textContent = state.previewExpanded ? '收起预览与映射' : '展开预览与映射';
}

function togglePreview() {
  state.previewExpanded = !state.previewExpanded;
  updatePreviewToggle();
}

async function refreshPreviewForSheet() {
  if (!state.upload?.file_id) return;
  setStatus('uploadStatus', '正在切换 sheet...');
  try {
    const sheetName = encodeURIComponent($('sheetSelect').value);
    const data = await apiFetch(`/api/uploads/${state.upload.file_id}/preview?sheet_name=${sheetName}`);
    data.filename = state.upload.filename;
    applyPreview(data);
    setStatus('uploadStatus', 'sheet 已切换。', 'success');
  } catch (error) {
    setStatus('uploadStatus', error.message, 'error');
  }
}

function renderMapping() {
  const grid = $('fieldMappingGrid');
  grid.innerHTML = STANDARD_FIELDS.map((field) => {
    const options = ['']
      .concat(state.columns)
      .map((column) => {
        const selected = state.fieldMapping[field] === column ? ' selected' : '';
        const label = column || '不映射';
        return `<option value="${escapeHtml(column)}"${selected}>${escapeHtml(label)}</option>`;
      })
      .join('');
    return `
      <label class="mapping-item">
        <span class="label">${escapeHtml(field)}</span>
        <select class="select-field mt-2 mapping-select" data-field="${escapeHtml(field)}">${options}</select>
      </label>
    `;
  }).join('');
}

function renderTable(tableId, rows, columns) {
  const table = $(tableId);
  if (!rows.length) {
    table.innerHTML = '<tbody><tr><td>暂无数据</td></tr></tbody>';
    return;
  }
  const visibleColumns = columns.length ? columns : Object.keys(rows[0]);
  table.innerHTML = `
    <thead><tr>${visibleColumns.map((column) => `<th>${escapeHtml(column)}</th>`).join('')}</tr></thead>
    <tbody>
      ${rows.map((row) => `
        <tr>${visibleColumns.map((column) => `<td>${escapeHtml(row[column] ?? '')}</td>`).join('')}</tr>
      `).join('')}
    </tbody>
  `;
}

function collectMapping() {
  const mapping = {};
  document.querySelectorAll('.mapping-select').forEach((select) => {
    mapping[select.dataset.field] = select.value;
  });
  return mapping;
}

function startProgress() {
  clearInterval(state.progressTimer);
  const bar = $('progressBar');
  let value = 8;
  bar.style.width = `${value}%`;
  state.progressTimer = setInterval(() => {
    value = Math.min(value + Math.random() * 10, 82);
    bar.style.width = `${value}%`;
  }, 700);
}

function finishProgress(ok) {
  clearInterval(state.progressTimer);
  $('progressBar').style.width = ok ? '100%' : '0%';
}

async function analyze() {
  if (!state.upload?.file_id) {
    setStatus('analysisStatus', '请先上传 xlsx 文件。', 'error');
    return;
  }
  const requirement = $('requirementInput').value.trim();
  if (!requirement) {
    setStatus('analysisStatus', '请先在需求拆解页填写专利检索需求。', 'error');
    activateTab('keywords');
    return;
  }

  const applicants = $('importantApplicantsInput').value
    .split(/\n|,|，|;|；/)
    .map((item) => item.trim())
    .filter(Boolean);

  $('analyzeBtn').disabled = true;
  $('downloadArea').classList.add('hidden');
  $('topRecordsSection').classList.add('hidden');
  setStatus('analysisStatus', '正在评分、总结并导出 Excel...');
  startProgress();
  try {
    const payload = {
      file_id: state.upload.file_id,
      sheet_name: $('sheetSelect').value,
      requirement,
      keyword_analysis: state.keywordResult || {},
      field_mapping: collectMapping(),
      max_ai_summary: Number($('maxSummaryInput').value || 0),
      important_applicants: applicants,
    };
    const data = await apiFetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    finishProgress(true);
    $('downloadArea').classList.remove('hidden');
    $('downloadLink').href = data.download_url;
    $('downloadLink').textContent = `下载 ${data.output_filename}`;
    renderTopRecords(data.top_records || []);
    const warningText = data.warnings?.length ? ` 提示：${data.warnings.join('；')}` : '';
    setStatus('analysisStatus', `分析完成，共处理 ${data.row_count} 条专利。${warningText}`, 'success');
    await loadHistory();
  } catch (error) {
    finishProgress(false);
    setStatus('analysisStatus', error.message, 'error');
  } finally {
    $('analyzeBtn').disabled = false;
  }
}

function renderTopRecords(records) {
  if (!records.length) return;
  $('topRecordsSection').classList.remove('hidden');
  renderTable('topRecordsTable', records, ['排名', '综合评分', '推荐等级', '专利名称', '申请人', '法律状态', '命中关键词', '阅读建议']);
}

async function loadHistory() {
  try {
    const data = await apiFetch('/api/history');
    const items = data.items || [];
    const rows = items.map((item) => ({
      时间: item.created_at || '',
      结果文件: item.output_filename || '',
      行数: item.row_count || 0,
      需求: item.requirement || '',
      操作: item.task_id,
    }));
    renderHistory(rows);
  } catch (error) {
    setGlobal(error.message, 'error');
  }
}

function renderHistory(rows) {
  const table = $('historyTable');
  if (!rows.length) {
    table.innerHTML = '<tbody><tr><td>暂无历史记录。</td></tr></tbody>';
    return;
  }
  table.innerHTML = `
    <thead><tr><th>时间</th><th>结果文件</th><th>行数</th><th>需求</th><th>操作</th></tr></thead>
    <tbody>
      ${rows.map((row) => `
        <tr>
          <td>${escapeHtml(row.时间)}</td>
          <td>${escapeHtml(row.结果文件)}</td>
          <td>${escapeHtml(row.行数)}</td>
          <td>${escapeHtml(row.需求)}</td>
          <td>
            <div class="flex gap-2">
              <a class="secondary-button" href="/api/history/${row.操作}/download">下载</a>
              <button class="secondary-button" data-delete-task="${escapeHtml(row.操作)}">删除</button>
            </div>
          </td>
        </tr>
      `).join('')}
    </tbody>
  `;
}

async function deleteTask(taskId) {
  try {
    await apiFetch(`/api/history/${taskId}`, { method: 'DELETE' });
    await loadHistory();
    setGlobal('历史记录已删除。', 'success');
  } catch (error) {
    setGlobal(error.message, 'error');
  }
}

function wireEvents() {
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.addEventListener('click', () => activateTab(button.dataset.tab));
  });
  $('saveSettingsBtn').addEventListener('click', saveSettings);
  $('testSettingsBtn').addEventListener('click', testSettings);
  $('extractKeywordsBtn').addEventListener('click', extractKeywords);
  $('copyKeywordsBtn').addEventListener('click', copyKeywords);
  $('uploadBtn').addEventListener('click', uploadFile);
  $('togglePreviewBtn').addEventListener('click', togglePreview);
  $('sheetSelect').addEventListener('change', refreshPreviewForSheet);
  $('analyzeBtn').addEventListener('click', analyze);
  $('refreshHistoryBtn').addEventListener('click', loadHistory);
  $('historyTable').addEventListener('click', (event) => {
    const button = event.target.closest('[data-delete-task]');
    if (button) deleteTask(button.dataset.deleteTask);
  });
}

document.addEventListener('DOMContentLoaded', async () => {
  wireEvents();
  await loadSettings();
  await loadHistory();
});
