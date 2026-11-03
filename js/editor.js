/**
 * 管理規約JSON 編集ツール (editor.js)
 * ./convt/ 内の JSON 構造 (docx_to_json.py 出力仕様) に完全準拠
 */

// =============================================================
// 1. 定数・番号変換ユーティリティ (docx_to_json.py 準拠)
// =============================================================
const HALF_TO_FULL_MAP = {
    '0': '０', '1': '１', '2': '２', '3': '３', '4': '４',
    '5': '５', '6': '６', '7': '７', '8': '８', '9': '９'
};
const FULL_TO_HALF_MAP = {
    '０': '0', '１': '1', '２': '2', '３': '3', '４': '4',
    '５': '5', '６': '6', '７': '7', '８': '8', '９': '9'
};

const KANJI_ONETEN = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九'];
const IROHA_LIST = [
    'イ', 'ロ', 'ハ', 'ニ', 'ホ', 'ヘ', 'ト', 'チ', 'リ', 'ヌ',
    'ル', 'ヲ', 'ワ', 'カ', 'ヨ', 'タ', 'レ', 'ソ', 'ツ', 'ネ'
];
const CIRCLE_NUM_LIST = [
    '①', '②', '③', '④', '⑤', '⑥', '⑦', '⑧', '⑨', '⑩',
    '⑪', '⑫', '⑬', '⑭', '⑮', '⑯', '⑰', '⑱', '⑲', '⑳'
];

function toFullWidthDigits(n) {
    return String(n).replace(/[0-9]/g, ch => HALF_TO_FULL_MAP[ch] || ch);
}

function toHalfWidthDigits(str) {
    return String(str || '').replace(/[０-９]/g, ch => FULL_TO_HALF_MAP[ch] || ch);
}

/**
 * 1〜99 の整数を漢数字（一、二、…十、十一、二十一…）に変換
 */
function numberToKanji(num) {
    const n = parseInt(num, 10);
    if (isNaN(n) || n < 1) return '一';
    if (n < 10) return KANJI_ONETEN[n];
    if (n === 10) return '十';
    if (n < 20) return '十' + KANJI_ONETEN[n % 10];
    if (n < 100) {
        const tens = Math.floor(n / 10);
        const ones = n % 10;
        return KANJI_ONETEN[tens] + '十' + KANJI_ONETEN[ones];
    }
    return String(n);
}

/**
 * docx_to_json.py の仕様通り、条番号文字列 (例: "第１条", "第19条の２") から
 * article_id (例: "art_0001", "art_0019_02") を自動生成する
 */
function generateArticleIdFromNumber(articleNumberStr, fallbackIndex = 1) {
    const normalized = toHalfWidthDigits(articleNumberStr).trim();
    const match = normalized.match(/第\s*(\d+)\s*条(?:\s*の\s*(\d+))?/);
    if (!match) {
        return `art_${String(fallbackIndex).padStart(4, '0')}`;
    }
    const mainNum = parseInt(match[1], 10);
    const subNum = match[2] ? parseInt(match[2], 10) : null;
    if (subNum !== null && !isNaN(subNum)) {
        return `art_${String(mainNum).padStart(4, '0')}_${String(subNum).padStart(2, '0')}`;
    }
    return `art_${String(mainNum).padStart(4, '0')}`;
}

/**
 * docx_to_json.py の仕様通り、主番号・枝番から条番号文字列を生成
 * (1〜9条は全角数字「第１条」、10条以上は半角数字「第10条」、枝番は全角「の２」)
 */
function formatArticleNumber(mainNum, subNum = null) {
    const m = parseInt(mainNum, 10);
    if (isNaN(m) || m < 1) return '第１条';
    let str = m < 10 ? `第${toFullWidthDigits(m)}条` : `第${m}条`;
    if (subNum !== null && subNum !== '' && !isNaN(parseInt(subNum, 10))) {
        str += `の${toFullWidthDigits(parseInt(subNum, 10))}`;
    }
    return str;
}

// =============================================================
// 2. アプリケーション状態管理 (State & Undo/Redo)
// =============================================================
const AppState = {
    data: null,           // 現在編集中の JSON オブジェクト
    originalData: null,   // 読み込み時の元 JSON オブジェクト（新旧対照表の比較基準）
    currentFileName: '管理組合規約.json',
    selected: {
        cIdx: 0,
        sIdx: 0,
        aIdx: 0
    },
    searchQuery: '',
    previewTab: 'preview', // 'preview' | 'diff' | 'json'
    undoStack: [],
    redoStack: [],
    maxHistory: 50
};

function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj));
}

/**
 * 変更前の状態を履歴スタックに保存
 */
function pushHistory() {
    if (!AppState.data) return;
    AppState.undoStack.push(deepClone(AppState.data));
    if (AppState.undoStack.length > AppState.maxHistory) {
        AppState.undoStack.shift();
    }
    AppState.redoStack = [];
    updateHistoryButtons();
    saveAutoBackup();
}

function undo() {
    if (AppState.undoStack.length === 0) return;
    AppState.redoStack.push(deepClone(AppState.data));
    AppState.data = AppState.undoStack.pop();
    clampSelection();
    renderAll();
    updateHistoryButtons();
    showToast('操作を元に戻しました');
}

function redo() {
    if (AppState.redoStack.length === 0) return;
    AppState.undoStack.push(deepClone(AppState.data));
    AppState.data = AppState.redoStack.pop();
    clampSelection();
    renderAll();
    updateHistoryButtons();
    showToast('操作をやり直しました');
}

function updateHistoryButtons() {
    $('#btn-undo').prop('disabled', AppState.undoStack.length === 0);
    $('#btn-redo').prop('disabled', AppState.redoStack.length === 0);
    const modCount = countModifiedArticles();
    if (modCount > 0) {
        $('#unsaved-badge').removeClass('d-none').text(`変更あり (${modCount}条)`);
    } else {
        $('#unsaved-badge').addClass('d-none');
    }
}

function saveAutoBackup() {
    try {
        if (AppState.data) {
            localStorage.setItem('bylaws_editor_backup', JSON.stringify({
                fileName: AppState.currentFileName,
                savedAt: new Date().toISOString(),
                data: AppState.data
            }));
        }
    } catch (e) {
        // localStorage 容量超過時は無視
    }
}

/**
 * 選択インデックスが範囲外にならないよう補正
 */
function clampSelection() {
    if (!AppState.data || !Array.isArray(AppState.data.chapters) || AppState.data.chapters.length === 0) {
        AppState.selected = { cIdx: 0, sIdx: 0, aIdx: 0 };
        return;
    }
    let { cIdx, sIdx, aIdx } = AppState.selected;
    cIdx = Math.max(0, Math.min(cIdx, AppState.data.chapters.length - 1));
    const chapter = AppState.data.chapters[cIdx];
    if (!chapter.sections || chapter.sections.length === 0) {
        chapter.sections = [{ section_number: null, section_title: null, articles: [] }];
    }
    sIdx = Math.max(0, Math.min(sIdx, chapter.sections.length - 1));
    const section = chapter.sections[sIdx];
    if (!section.articles) section.articles = [];
    aIdx = Math.max(0, Math.min(aIdx, Math.max(0, section.articles.length - 1)));
    AppState.selected = { cIdx, sIdx, aIdx };
}

/**
 * 出力・保存用に JSON データを docx_to_json.py のスキーマへ完全正規化する
 */
function cleanDataForExport(rawData) {
    const cleaned = {
        bylaws_title: (rawData.bylaws_title || '').trim(),
        chapters: []
    };

    (rawData.chapters || []).forEach(chap => {
        const cleanChap = {
            chapter_number: chap.chapter_number || '',
            chapter_title: chap.chapter_title || '',
            sections: []
        };

        (chap.sections || []).forEach(sec => {
            const hasSectionTitle = Boolean(
                (sec.section_number && String(sec.section_number).trim()) ||
                (sec.section_title && String(sec.section_title).trim())
            );
            const cleanSec = {
                section_number: hasSectionTitle ? (sec.section_number || null) : null,
                section_title: hasSectionTitle ? (sec.section_title || null) : null,
                articles: []
            };

            (sec.articles || []).forEach(art => {
                const cleanArt = {
                    article_id: art.article_id || generateArticleIdFromNumber(art.article_number),
                    article_number: art.article_number || '',
                    title: art.title !== undefined && art.title !== null ? String(art.title) : '',
                    paragraphs: []
                };

                (art.paragraphs || []).forEach((para, pIdx) => {
                    const cleanPara = {
                        paragraph_no: para.paragraph_no !== undefined ? Number(para.paragraph_no) : (pIdx + 1),
                        text: para.text !== undefined && para.text !== null ? String(para.text) : '',
                        items: []
                    };

                    (para.items || []).forEach(item => {
                        const isTermMode = item._isTermMode !== undefined
                            ? item._isTermMode
                            : (item.term !== undefined || item.definition !== undefined);

                        const cleanItem = {
                            item_no: item.item_no || ''
                        };

                        if (isTermMode) {
                            cleanItem.term = item.term || '';
                            cleanItem.definition = item.definition || '';
                        } else {
                            cleanItem.text = item.text || '';
                        }

                        if (Array.isArray(item.sub_items) && item.sub_items.length > 0) {
                            cleanItem.sub_items = item.sub_items.map(sub => {
                                const cleanSub = {
                                    sub_item_no: sub.sub_item_no || '',
                                    text: sub.text || ''
                                };
                                if (Array.isArray(sub.details) && sub.details.length > 0) {
                                    cleanSub.details = sub.details.map(det => ({
                                        detail_no: det.detail_no || '',
                                        text: det.text || ''
                                    }));
                                }
                                return cleanSub;
                            });
                        }

                        cleanPara.items.push(cleanItem);
                    });

                    cleanArt.paragraphs.push(cleanPara);
                });

                cleanSec.articles.push(cleanArt);
            });

            cleanChap.sections.push(cleanSec);
        });

        cleaned.chapters.push(cleanChap);
    });

    return cleaned;
}

// =============================================================
// 3. 変更検知・新旧比較ロジック
// =============================================================
function getOriginalArticleMap() {
    const map = new Map();
    if (!AppState.originalData) return map;
    const cleanOrig = cleanDataForExport(AppState.originalData);
    (cleanOrig.chapters || []).forEach(chap => {
        (chap.sections || []).forEach(sec => {
            (sec.articles || []).forEach(art => {
                map.set(art.article_id, art);
            });
        });
    });
    return map;
}

function isArticleModified(article) {
    if (!AppState.originalData || !article) return false;
    const origMap = getOriginalArticleMap();
    const origArt = origMap.get(article.article_id);
    if (!origArt) return true; // 新規追加された条
    const cleanCurrent = cleanDataForExport({
        bylaws_title: '',
        chapters: [{
            chapter_number: '',
            chapter_title: '',
            sections: [{ section_number: null, section_title: null, articles: [article] }]
        }]
    }).chapters[0].sections[0].articles[0];

    return JSON.stringify(origArt) !== JSON.stringify(cleanCurrent);
}

function countModifiedArticles() {
    if (!AppState.data || !AppState.originalData) return 0;
    const cleanCur = cleanDataForExport(AppState.data);
    const origMap = getOriginalArticleMap();
    const curIds = new Set();
    let count = 0;

    (cleanCur.chapters || []).forEach(chap => {
        (chap.sections || []).forEach(sec => {
            (sec.articles || []).forEach(art => {
                curIds.add(art.article_id);
                const orig = origMap.get(art.article_id);
                if (!orig || JSON.stringify(orig) !== JSON.stringify(art)) {
                    count++;
                }
            });
        });
    });

    // 削除された条もカウント
    origMap.forEach((_, id) => {
        if (!curIds.has(id)) count++;
    });

    return count;
}

// =============================================================
// 4. 画面レンダリング (左ツリー / 中央フォーム / 右プレビュー)
// =============================================================
function renderAll() {
    if (!AppState.data) return;
    clampSelection();
    renderHeaderInfo();
    renderTreeSidebar();
    renderMainEditor();
    renderRightPane();
    updateHistoryButtons();
}

function renderHeaderInfo() {
    $('#current-file-badge').text(AppState.currentFileName);
    $('#bylaws-title-input').val(AppState.data.bylaws_title || '');
}

/**
 * 左ペイン：章・節・条のツリー目次描画
 */
function renderTreeSidebar() {
    const $tree = $('#sidebar-tree').empty();
    const query = (AppState.searchQuery || '').trim().toLowerCase();
    let totalArticles = 0;
    let matchedArticles = 0;

    (AppState.data.chapters || []).forEach((chap, cIdx) => {
        const $chapBox = $('<div class="tree-chapter-box"></div>');
        const isCurrentChap = cIdx === AppState.selected.cIdx;

        const $chapHeader = $(`
            <div class="tree-chapter-header ${isCurrentChap ? 'active' : ''}" data-cidx="${cIdx}">
                <span class="text-truncate">${escapeHtml(chap.chapter_number || '')} ${escapeHtml(chap.chapter_title || '')}</span>
                <span class="badge bg-dark bg-opacity-50 fw-normal">${countChapterArticles(chap)}条</span>
            </div>
        `);
        $chapBox.append($chapHeader);

        let chapHasMatch = false;

        (chap.sections || []).forEach((sec, sIdx) => {
            if (sec.section_title || sec.section_number) {
                const isCurrentSec = isCurrentChap && sIdx === AppState.selected.sIdx;
                const $secHeader = $(`
                    <div class="tree-section-header ${isCurrentSec ? 'active' : ''}" data-cidx="${cIdx}" data-sidx="${sIdx}">
                        <span class="text-truncate"><i class="ph ph-folder-Simple me-1"></i>${escapeHtml(sec.section_number || '')} ${escapeHtml(sec.section_title || '')}</span>
                    </div>
                `);
                $chapBox.append($secHeader);
            }

            (sec.articles || []).forEach((art, aIdx) => {
                totalArticles++;
                const matchText = JSON.stringify(art).toLowerCase();
                if (query && !matchText.includes(query)) {
                    return;
                }
                matchedArticles++;
                chapHasMatch = true;

                const isSelected = cIdx === AppState.selected.cIdx &&
                                   sIdx === AppState.selected.sIdx &&
                                   aIdx === AppState.selected.aIdx;
                const modified = isArticleModified(art);

                const $artItem = $(`
                    <div class="tree-article-item ${isSelected ? 'active' : ''} ${modified ? 'modified' : ''}"
                         data-cidx="${cIdx}" data-sidx="${sIdx}" data-aidx="${aIdx}">
                        <div class="text-truncate pe-2">
                            <span class="fw-bold me-1">${escapeHtml(art.article_number || '')}</span>
                            <span class="text-secondary small">${art.title ? `（${escapeHtml(art.title)}）` : ''}</span>
                        </div>
                        <span class="modified-dot" title="変更あり"></span>
                    </div>
                `);
                $chapBox.append($artItem);
            });
        });

        if (!query || chapHasMatch || (chap.sections || []).every(s => (s.articles || []).length === 0)) {
            $tree.append($chapBox);
        }
    });

    $('#tree-stats-badge').text(query ? `${matchedArticles} / ${totalArticles} 条` : `全 ${totalArticles} 条`);
}

function countChapterArticles(chap) {
    return (chap.sections || []).reduce((acc, s) => acc + (s.articles ? s.articles.length : 0), 0);
}

/**
 * 中央ペイン：選択中の章・節・条の編集フォーム描画
 */
function renderMainEditor() {
    const $main = $('#editor-main-content').empty();
    const { cIdx, sIdx, aIdx } = AppState.selected;
    const chapter = AppState.data.chapters[cIdx];

    if (!chapter) {
        $main.html(`
            <div class="text-center py-5 text-muted">
                <i class="ph ph-Warning-circle fs-1 d-block mb-2"></i>
                <p>章が存在しません。「＋章を追加」ボタンから作成してください。</p>
            </div>
        `);
        return;
    }

    const section = chapter.sections[sIdx];
    const hasSection = Boolean(section && (section.section_number || section.section_title));
    const article = section && section.articles ? section.articles[aIdx] : null;

    // 1. 章・節の管理カード（アコーディオンまたはコンパクトバー）
    const $chapSecCard = $(`
        <div class="edit-section-card p-3 mb-3">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 pb-2 mb-2 border-bottom">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge bg-dark">所属する章・節の設定</span>
                    <span class="text-muted small">（現在の位置：第${cIdx + 1}章 / 節インデックス ${sIdx + 1}）</span>
                </div>
                <div class="d-flex flex-wrap gap-1">
                    <button type="button" class="btn btn-outline-primary btn-sm" id="btn-add-chapter">
                        <i class="ph ph-plus"></i> 章を追加
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="btn-add-section">
                        <i class="ph ph-folders"></i> この章に節を追加
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm" id="btn-delete-chapter" title="この章を削除">
                        <i class="ph ph-trash"></i> 章削除
                    </button>
                </div>
            </div>

            <div class="row g-2 align-items-end">
                <div class="col-sm-3 col-md-2">
                    <label class="form-label small fw-bold mb-1">章番号</label>
                    <input type="text" class="form-control form-control-sm" id="inp-chapter-number"
                           value="${escapeAttr(chapter.chapter_number || '')}" placeholder="例：第１章">
                </div>
                <div class="col-sm-5 col-md-4">
                    <label class="form-label small fw-bold mb-1">章タイトル</label>
                    <input type="text" class="form-control form-control-sm" id="inp-chapter-title"
                           value="${escapeAttr(chapter.chapter_title || '')}" placeholder="例：総則">
                </div>
                <div class="col-sm-4 col-md-2">
                    <div class="form-check form-switch mb-1">
                        <input class="form-check-input" type="checkbox" id="chk-has-section" ${hasSection ? 'checked' : ''}>
                        <label class="form-check-label small fw-bold" for="chk-has-section">「節」を設ける</label>
                    </div>
                </div>
                <div class="col-sm-6 col-md-2 section-fields ${hasSection ? '' : 'd-none'}">
                    <label class="form-label small fw-bold mb-1">節番号</label>
                    <input type="text" class="form-control form-control-sm" id="inp-section-number"
                           value="${escapeAttr(section.section_number || '')}" placeholder="例：第１節">
                </div>
                <div class="col-sm-6 col-md-2 section-fields ${hasSection ? '' : 'd-none'}">
                    <label class="form-label small fw-bold mb-1">節タイトル</label>
                    <div class="input-group input-group-sm">
                        <input type="text" class="form-control" id="inp-section-title"
                               value="${escapeAttr(section.section_title || '')}" placeholder="例：総会">
                        ${chapter.sections.length > 1 ? `
                        <button class="btn btn-outline-danger" type="button" id="btn-delete-section" title="この節を削除">
                            <i class="ph ph-trash"></i>
                        </button>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `);
    $main.append($chapSecCard);

    // 条がまだない場合
    if (!article) {
        $main.append(`
            <div class="edit-section-card p-5 text-center">
                <i class="ph ph-file-plus fs-1 text-primary d-block mb-2"></i>
                <h5 class="fw-bold">この章（節）にはまだ条文がありません</h5>
                <p class="text-muted small mb-3">下のボタンを押して最初の条文を追加してください。</p>
                <button type="button" class="btn btn-primary" id="btn-add-first-article">
                    <i class="ph ph-plus-circle me-1"></i> 条文を追加する
                </button>
            </div>
        `);
        return;
    }

    // 2. 条 (Article) の基本情報編集カード
    const totalInSec = section.articles.length;
    const $artCard = $(`
        <div class="edit-section-card p-3 p-md-4">
            <!-- 条ヘッダー操作バー -->
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 pb-3 mb-3 border-bottom">
                <div class="d-flex align-items-center gap-2">
                    <span class="badge bg-primary fs-6 px-3 py-2">${escapeHtml(article.article_number || '条番号未設定')}</span>
                    <h4 class="fw-bold mb-0">${article.title ? `（${escapeHtml(article.title)}）` : '<span class="text-muted fs-6">（見出しなし）</span>'}</h4>
                </div>
                <div class="d-flex flex-wrap align-items-center gap-1">
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="btn-move-art-up" ${aIdx === 0 ? 'disabled' : ''} title="この条を1つ上へ移動">
                        <i class="ph ph-arrow-up"></i> 上へ
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm" id="btn-move-art-down" ${aIdx >= totalInSec - 1 ? 'disabled' : ''} title="この条を1つ下へ移動">
                        <i class="ph ph-arrow-down"></i> 下へ
                    </button>
                    <button type="button" class="btn btn-success btn-sm" id="btn-insert-art-after" title="この条のすぐ下に新しい条を追加">
                        <i class="ph ph-plus-circle"></i> 次へ条を追加
                    </button>
                    <button type="button" class="btn btn-outline-primary btn-sm" id="btn-insert-branch-art" title="法改正等で条番号をずらさずに枝番（第○条の２）を挿入">
                        <i class="ph ph-git-branch"></i> 枝番（の２）を追加
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm ms-2" id="btn-delete-article" title="この条を削除">
                        <i class="ph ph-trash"></i> この条を削除
                    </button>
                </div>
            </div>

            <!-- 条番号・見出し・ID フォーム -->
            <div class="row g-3 mb-4 p-3 bg-light rounded-3 border">
                <div class="col-sm-4 col-md-3">
                    <label class="form-label small fw-bold mb-1">
                        条番号 <span class="text-danger">*</span>
                    </label>
                    <input type="text" class="form-control fw-bold" id="inp-article-number"
                           value="${escapeAttr(article.article_number || '')}" placeholder="例：第１条 / 第19条の２">
                    <div class="form-text small">1〜9条は全角、10条〜は半角推奨</div>
                </div>
                <div class="col-sm-5 col-md-5">
                    <label class="form-label small fw-bold mb-1">
                        条の見出し（カッコ不要）
                    </label>
                    <div class="input-group">
                        <span class="input-group-text text-muted">（</span>
                        <input type="text" class="form-control fw-bold" id="inp-article-title"
                               value="${escapeAttr(article.title || '')}" placeholder="例：目的">
                        <span class="input-group-text text-muted">）</span>
                    </div>
                    <div class="form-text small">表示時に自動で「（　）」が付きます</div>
                </div>
                <div class="col-sm-3 col-md-4">
                    <label class="form-label small fw-bold mb-1 d-flex justify-content-between">
                        <span>内部ID (<code>article_id</code>)</span>
                        <span class="badge bg-secondary bg-opacity-25 text-dark fw-normal">自動生成</span>
                    </label>
                    <input type="text" class="form-control bg-white text-secondary font-monospace" id="inp-article-id"
                           value="${escapeAttr(article.article_id || '')}" readonly>
                    <div class="form-text small">条番号から自動計算されます（例: art_0001）</div>
                </div>
            </div>

            <!-- 項 (paragraphs) 一覧ヘッダー -->
            <div class="d-flex align-items-center justify-content-between mb-3">
                <h6 class="fw-bold mb-0 d-flex align-items-center gap-2">
                    <i class="ph ph-list-numbers text-primary fs-5"></i>
                    <span>項（Paragraphs）・号（Items）の編集</span>
                    <span class="badge bg-primary bg-opacity-10 text-primary">${(article.paragraphs || []).length} 項</span>
                </h6>
                <button type="button" class="btn btn-primary btn-sm" id="btn-add-paragraph">
                    <i class="ph ph-plus"></i> 新しい「項」を末尾に追加
                </button>
            </div>

            <!-- 項リストコンテナ -->
            <div id="paragraphs-editor-list"></div>
        </div>
    `);

    const $paraList = $artCard.find('#paragraphs-editor-list');
    (article.paragraphs || []).forEach((para, pIdx) => {
        $paraList.append(buildParagraphEditorCard(para, pIdx, article.paragraphs.length, article));
    });

    $main.append($artCard);
    autoResizeAllTextareas();
}

/**
 * [項] (Paragraph) 編集カードの生成
 */
function buildParagraphEditorCard(para, pIdx, totalParas, article) {
    const paraNo = para.paragraph_no !== undefined ? para.paragraph_no : (pIdx + 1);
    const isFirst = Number(paraNo) === 1;
    const noteText = isFirst
        ? `第1項（閲覧画面では項番号「1」は表示されず、「${escapeHtml(article.article_number || '第○条')}　本文…」と表示されます）`
        : `第${paraNo}項（閲覧画面では丸バッジ「${paraNo}」が表示されます）`;

    const $card = $(`
        <div class="para-edit-card" data-pidx="${pIdx}">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="level-badge-para">第 ${paraNo} 項</span>
                    <span class="text-muted small">${noteText}</span>
                </div>
                <div class="d-flex align-items-center gap-1">
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-move-para-up" data-pidx="${pIdx}" ${pIdx === 0 ? 'disabled' : ''} title="項を上へ移動">
                        <i class="ph ph-caret-up"></i>
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-move-para-down" data-pidx="${pIdx}" ${pIdx >= totalParas - 1 ? 'disabled' : ''} title="項を下へ移動">
                        <i class="ph ph-caret-down"></i>
                    </button>
                    <button type="button" class="btn btn-outline-success btn-sm py-0 px-2 btn-add-item" data-pidx="${pIdx}">
                        <i class="ph ph-plus"></i> 号（一、二…）を追加
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 btn-delete-para" data-pidx="${pIdx}" ${totalParas <= 1 ? 'disabled' : ''} title="この項を削除">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            </div>

            <div class="mb-2">
                <textarea class="form-control auto-resize inp-para-text" data-pidx="${pIdx}" rows="2"
                          placeholder="第${paraNo}項の本文を入力してください...">${escapeHtml(para.text || '')}</textarea>
            </div>

            <div class="items-editor-container ps-2 ps-md-3"></div>
        </div>
    `);

    const $itemsContainer = $card.find('.items-editor-container');
    if (Array.isArray(para.items) && para.items.length > 0) {
        // 号ヘッダー＆一括連番ボタン
        $itemsContainer.append(`
            <div class="d-flex align-items-center justify-content-between mt-2 mb-1">
                <span class="small fw-bold text-success">
                    <i class="ph ph-list-bullets me-1"></i>各号リスト（${para.items.length}件）
                </span>
                <button type="button" class="btn btn-link btn-sm text-decoration-none p-0 btn-renumber-items" data-pidx="${pIdx}">
                    <i class="ph ph-arrows-clockwise"></i> 号番号を「一、二、三…」で自動連番振り直し
                </button>
            </div>
        `);

        para.items.forEach((item, iIdx) => {
            $itemsContainer.append(buildItemEditorCard(item, pIdx, iIdx, para.items.length));
        });
    }

    return $card;
}

/**
 * [号] (Item) 編集カードの生成
 * 通常形式 (text) と 用語定義形式 (term + definition: 第2条用) の両方に対応
 */
function buildItemEditorCard(item, pIdx, iIdx, totalItems) {
    const isTermMode = item._isTermMode !== undefined
        ? item._isTermMode
        : (item.term !== undefined || item.definition !== undefined);

    const $itemCard = $(`
        <div class="item-edit-card" data-pidx="${pIdx}" data-iidx="${iIdx}">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="level-badge-item">号</span>
                    <div class="input-group input-group-sm" style="width: 120px;">
                        <span class="input-group-text text-muted">番号</span>
                        <input type="text" class="form-control fw-bold text-center inp-item-no"
                               data-pidx="${pIdx}" data-iidx="${iIdx}"
                               value="${escapeAttr(item.item_no || '')}" placeholder="一">
                    </div>
                    <div class="form-check form-switch ms-2 mb-0">
                        <input class="form-check-input chk-item-term-mode" type="checkbox"
                               data-pidx="${pIdx}" data-iidx="${iIdx}"
                               id="termMode_${pIdx}_${iIdx}" ${isTermMode ? 'checked' : ''}>
                        <label class="form-check-label small text-muted" for="termMode_${pIdx}_${iIdx}">
                            用語・定義形式（第2条用）
                        </label>
                    </div>
                </div>

                <div class="d-flex align-items-center gap-1">
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-move-item-up"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" ${iIdx === 0 ? 'disabled' : ''} title="上へ移動">
                        <i class="ph ph-caret-up"></i>
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-move-item-down"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" ${iIdx >= totalItems - 1 ? 'disabled' : ''} title="下へ移動">
                        <i class="ph ph-caret-down"></i>
                    </button>
                    <button type="button" class="btn btn-outline-warning btn-sm py-0 px-2 text-dark btn-add-subitem"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" title="イ、ロ、ハ または ①、② などの細目を追加">
                        <i class="ph ph-plus"></i> 細目(イ/①)追加
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 btn-delete-item"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" title="この号を削除">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            </div>

            ${isTermMode ? `
                <div class="row g-2">
                    <div class="col-sm-4 col-md-3">
                        <label class="form-label small fw-bold text-primary mb-1">用語 (<code>term</code>)</label>
                        <input type="text" class="form-control form-control-sm fw-bold inp-item-term"
                               data-pidx="${pIdx}" data-iidx="${iIdx}"
                               value="${escapeAttr(item.term || '')}" placeholder="例：区分所有権">
                    </div>
                    <div class="col-sm-8 col-md-9">
                        <label class="form-label small fw-bold text-primary mb-1">定義文 (<code>definition</code>)</label>
                        <textarea class="form-control form-control-sm auto-resize inp-item-definition"
                                  data-pidx="${pIdx}" data-iidx="${iIdx}" rows="2"
                                  placeholder="例：建物の区分所有等に関する法律…">${escapeHtml(item.definition || '')}</textarea>
                    </div>
                </div>
            ` : `
                <div>
                    <textarea class="form-control form-control-sm auto-resize inp-item-text"
                              data-pidx="${pIdx}" data-iidx="${iIdx}" rows="2"
                              placeholder="号の本文を入力してください...">${escapeHtml(item.text || '')}</textarea>
                </div>
            `}

            <div class="subitems-editor-container ps-2 ps-md-3"></div>
        </div>
    `);

    const $subContainer = $itemCard.find('.subitems-editor-container');
    if (Array.isArray(item.sub_items) && item.sub_items.length > 0) {
        item.sub_items.forEach((sub, subIdx) => {
            $subContainer.append(buildSubItemEditorCard(sub, pIdx, iIdx, subIdx, item.sub_items.length));
        });
    }

    return $itemCard;
}

/**
 * [細目1] (sub_items: イ、ロ、ハ / ①、②) 編集カードの生成
 */
function buildSubItemEditorCard(sub, pIdx, iIdx, subIdx, totalSubs) {
    const $subCard = $(`
        <div class="subitem-edit-card" data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}">
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-1">
                <div class="d-flex align-items-center gap-2">
                    <span class="level-badge-subitem">細目 (sub_item)</span>
                    <div class="input-group input-group-sm" style="width: 110px;">
                        <span class="input-group-text text-muted">記号</span>
                        <input type="text" class="form-control fw-bold text-center inp-subitem-no"
                               data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}"
                               value="${escapeAttr(sub.sub_item_no || '')}" placeholder="イ / ①">
                    </div>
                </div>
                <div class="d-flex align-items-center gap-1">
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-move-subitem-up"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" ${subIdx === 0 ? 'disabled' : ''}>
                        <i class="ph ph-caret-up"></i>
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-move-subitem-down"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" ${subIdx >= totalSubs - 1 ? 'disabled' : ''}>
                        <i class="ph ph-caret-down"></i>
                    </button>
                    <button type="button" class="btn btn-outline-secondary btn-sm py-0 px-2 btn-add-detail"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" title="（１）、（２）などの詳細を追加">
                        <i class="ph ph-plus"></i> 詳細（１）追加
                    </button>
                    <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 btn-delete-subitem"
                            data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}">
                        <i class="ph ph-trash"></i>
                    </button>
                </div>
            </div>

            <div>
                <textarea class="form-control form-control-sm auto-resize inp-subitem-text"
                          data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" rows="1"
                          placeholder="細目の本文を入力...">${escapeHtml(sub.text || '')}</textarea>
            </div>

            <div class="details-editor-container ps-2 ps-md-3"></div>
        </div>
    `);

    const $detContainer = $subCard.find('.details-editor-container');
    if (Array.isArray(sub.details) && sub.details.length > 0) {
        sub.details.forEach((det, detIdx) => {
            $detContainer.append(buildDetailEditorCard(det, pIdx, iIdx, subIdx, detIdx, sub.details.length));
        });
    }

    return $subCard;
}

/**
 * [細目2] (details: （１）、（２）) 編集カードの生成
 */
function buildDetailEditorCard(det, pIdx, iIdx, subIdx, detIdx, totalDets) {
    return $(`
        <div class="detail-edit-card" data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" data-detidx="${detIdx}">
            <div class="d-flex align-items-center gap-2">
                <span class="level-badge-detail">詳細</span>
                <input type="text" class="form-control form-control-sm fw-bold text-center inp-detail-no"
                       style="width: 75px;"
                       data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" data-detidx="${detIdx}"
                       value="${escapeAttr(det.detail_no || '')}" placeholder="（１）">
                <textarea class="form-control form-control-sm auto-resize flex-grow-1 inp-detail-text"
                          data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" data-detidx="${detIdx}" rows="1"
                          placeholder="詳細テキストを入力...">${escapeHtml(det.text || '')}</textarea>
                <button type="button" class="btn btn-outline-danger btn-sm py-0 px-2 btn-delete-detail"
                        data-pidx="${pIdx}" data-iidx="${iIdx}" data-subidx="${subIdx}" data-detidx="${detIdx}">
                    <i class="ph ph-trash"></i>
                </button>
            </div>
        </div>
    `);
}

// =============================================================
// 5. 右ペイン：リアルタイムプレビュー / 新旧対照表 / JSONコード
// =============================================================
function renderRightPane() {
    const $body = $('#preview-pane-body').empty();
    const tab = AppState.previewTab;

    $('.preview-tab-btn').removeClass('active');
    $(`.preview-tab-btn[data-tab="${tab}"]`).addClass('active');

    if (tab === 'preview') {
        renderLiveArticlePreview($body);
    } else if (tab === 'diff') {
        renderDiffTable($body);
    } else if (tab === 'json') {
        renderCleanJsonView($body);
    }
}

/**
 * code_artifact.js と同じ HTML 構造・クラスで選択中の章・条をリアルタイム描画
 */
function renderLiveArticlePreview($container) {
    const { cIdx, sIdx, aIdx } = AppState.selected;
    const chapter = AppState.data.chapters[cIdx];
    if (!chapter) return;
    const section = chapter.sections[sIdx];
    const article = section && section.articles ? section.articles[aIdx] : null;

    const $wrapper = $('<div></div>');
    $wrapper.append(`
        <div class="d-flex align-items-center justify-content-between mb-2">
            <span class="small fw-bold text-secondary">
                <i class="ph ph-eye me-1"></i>本番ビューア (code_artifact.html) 表示イメージ
            </span>
            <span class="badge bg-light text-dark border">${escapeHtml(chapter.chapter_number || '')} ${escapeHtml(chapter.chapter_title || '')}</span>
        </div>
    `);

    if (section && section.section_title) {
        $wrapper.append(`
            <div class="section-header d-flex align-items-center gap-2 pb-2 mb-3">
                <span class="badge section-num-badge px-2 py-1">${escapeHtml(section.section_number || '')}</span>
                <h5 class="section-title-text mb-0">${escapeHtml(section.section_title || '')}</h5>
            </div>
        `);
    }

    if (!article) {
        $wrapper.append('<div class="text-muted small py-4 text-center">条文が選択されていません</div>');
        $container.append($wrapper);
        return;
    }

    const artTitle = article.title ? `（${escapeHtml(article.title)}）` : '';
    const $artBox = $(`
        <article class="article-box p-3 bg-white shadow-sm">
            <div class="article-header d-flex align-items-start justify-content-between gap-2 pb-2 mb-3">
                <span class="article-title-text">${artTitle}</span>
                <span class="badge bg-light text-secondary border font-monospace">${escapeHtml(article.article_id || '')}</span>
            </div>
            <div class="paragraphs-list d-flex flex-column gap-3"></div>
        </article>
    `);

    const $pList = $artBox.find('.paragraphs-list');
    (article.paragraphs || []).forEach((para, pIdx) => {
        const paraNo = para.paragraph_no !== undefined ? para.paragraph_no : (pIdx + 1);
        const isFirst = Number(paraNo) === 1;
        const paraBadge = !isFirst ? `<span class="paragraph-no-badge">${escapeHtml(String(paraNo))}</span>` : '';
        const textHtml = isFirst && article.article_number
            ? `<span class="article-num-text">${escapeHtml(article.article_number)}</span>　${escapeHtml(para.text || '')}`
            : escapeHtml(para.text || '');

        const $para = $(`
            <div class="paragraph-item d-flex flex-column gap-2">
                <div class="paragraph-main d-flex align-items-start gap-2">
                    ${paraBadge}
                    <p class="paragraph-text flex-grow-1">${textHtml}</p>
                </div>
                <div class="items-list ps-3 d-flex flex-column gap-2"></div>
            </div>
        `);

        const $iList = $para.find('.items-list');
        if (Array.isArray(para.items) && para.items.length > 0) {
            para.items.forEach(item => {
                const itemNoKanji = item.item_no ? String(item.item_no).replace(/^第/, '').replace(/号$/, '') : '・';
                const isTerm = item._isTermMode !== undefined
                    ? item._isTermMode
                    : (item.term !== undefined || item.definition !== undefined);
                const termBadge = isTerm && item.term
                    ? `<span class="item-term-badge">【${escapeHtml(item.term)}】</span>`
                    : '';
                const bodyText = isTerm ? (item.definition || '') : (item.text || '');

                const $item = $(`
                    <div class="item-block p-2 d-flex flex-column gap-2">
                        <div class="item-main d-flex align-items-start gap-2">
                            <span class="item-no-badge">${escapeHtml(itemNoKanji)}</span>
                            <div class="item-body-text flex-grow-1">${termBadge}${escapeHtml(bodyText)}</div>
                        </div>
                        <div class="sub-items-list ps-3 ms-2 mt-1 d-flex flex-column gap-1"></div>
                    </div>
                `);

                const $subList = $item.find('.sub-items-list');
                if (Array.isArray(item.sub_items) && item.sub_items.length > 0) {
                    item.sub_items.forEach(sub => {
                        const $sub = $(`
                            <div class="sub-item-block d-flex flex-column gap-1">
                                <div class="sub-item-main d-flex align-items-start gap-2">
                                    <span class="sub-item-no">${escapeHtml(sub.sub_item_no || '・')}</span>
                                    <span class="sub-item-text">${escapeHtml(sub.text || '')}</span>
                                </div>
                                <div class="details-list ps-3 ms-1 d-flex flex-column gap-1"></div>
                            </div>
                        `);
                        const $detList = $sub.find('.details-list');
                        if (Array.isArray(sub.details) && sub.details.length > 0) {
                            sub.details.forEach(det => {
                                $detList.append(`
                                    <div class="detail-item d-flex align-items-start gap-1">
                                        <span class="detail-no">${escapeHtml(det.detail_no || '')}</span>
                                        <span class="detail-text">${escapeHtml(det.text || '')}</span>
                                    </div>
                                `);
                            });
                        } else {
                            $detList.remove();
                        }
                        $subList.append($sub);
                    });
                } else {
                    $subList.remove();
                }

                $iList.append($item);
            });
        } else {
            $iList.remove();
        }

        $pList.append($para);
    });

    $wrapper.append($artBox);
    $container.append($wrapper);
}

/**
 * 新旧対照表（変更があった条文の比較テーブル）を描画
 */
function renderDiffTable($container) {
    const cleanCur = cleanDataForExport(AppState.data);
    const origMap = getOriginalArticleMap();
    const curMap = new Map();
    const allIds = [];

    (cleanCur.chapters || []).forEach(c => {
        (c.sections || []).forEach(s => {
            (s.articles || []).forEach(a => {
                curMap.set(a.article_id, a);
                if (!allIds.includes(a.article_id)) allIds.push(a.article_id);
            });
        });
    });
    origMap.forEach((_, id) => {
        if (!allIds.includes(id)) allIds.push(id);
    });

    const changedRows = [];
    allIds.forEach(id => {
        const orig = origMap.get(id);
        const cur = curMap.get(id);
        if (!orig && cur) {
            changedRows.push({ status: '新設', orig: null, cur });
        } else if (orig && !cur) {
            changedRows.push({ status: '削除', orig, cur: null });
        } else if (JSON.stringify(orig) !== JSON.stringify(cur)) {
            changedRows.push({ status: '改正', orig, cur });
        }
    });

    const $header = $(`
        <div class="d-flex align-items-center justify-content-between mb-3">
            <div>
                <h6 class="fw-bold mb-0">新旧対照表（変更箇所の自動抽出）</h6>
                <span class="text-muted small">読込時のデータと現在の編集内容を比較しています</span>
            </div>
            <button type="button" class="btn btn-outline-dark btn-sm" onclick="window.print()">
                <i class="ph ph-printer"></i> 対照表を印刷
            </button>
        </div>
    `);
    $container.append($header);

    if (changedRows.length === 0) {
        $container.append(`
            <div class="alert alert-light border text-center py-4">
                <i class="ph ph-check-circle text-success fs-3 d-block mb-1"></i>
                現在、読込時から変更された条文はありません。
            </div>
        `);
        return;
    }

    const $table = $(`
        <table class="diff-table">
            <thead>
                <tr>
                    <th>改正案（編集後）</th>
                    <th>現行（編集前）</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    `);
    const $tbody = $table.find('tbody');

    changedRows.forEach(row => {
        const curText = row.cur ? formatArticlePlainText(row.cur) : '（削　除）';
        const origText = row.orig ? formatArticlePlainText(row.orig) : '（新　設）';
        const badgeClass = row.status === '新設' ? 'bg-success' : (row.status === '削除' ? 'bg-danger' : 'bg-warning text-dark');

        $tbody.append(`
            <tr>
                <td>
                    <span class="badge ${badgeClass} mb-1">${row.status}</span>
                    <div>${highlightLineDiff(origText, curText, 'new')}</div>
                </td>
                <td>
                    <span class="badge bg-secondary mb-1">変更前</span>
                    <div>${highlightLineDiff(origText, curText, 'old')}</div>
                </td>
            </tr>
        `);
    });

    $container.append($table);
}

function formatArticlePlainText(art) {
    const lines = [];
    if (art.title) lines.push(`（${art.title}）`);
    (art.paragraphs || []).forEach((p, idx) => {
        const pNo = p.paragraph_no !== undefined ? p.paragraph_no : (idx + 1);
        if (Number(pNo) === 1) {
            lines.push(`${art.article_number}　${p.text || ''}`);
        } else {
            lines.push(`${pNo}　${p.text || ''}`);
        }
        (p.items || []).forEach(item => {
            if (item.term !== undefined || item.definition !== undefined) {
                lines.push(`　${item.item_no}　【${item.term || ''}】 ${item.definition || ''}`);
            } else {
                lines.push(`　${item.item_no}　${item.text || ''}`);
            }
            (item.sub_items || []).forEach(sub => {
                lines.push(`　　${sub.sub_item_no}　${sub.text || ''}`);
                (sub.details || []).forEach(det => {
                    lines.push(`　　　${det.detail_no}　${det.text || ''}`);
                });
            });
        });
    });
    return lines.join('\n');
}

function highlightLineDiff(oldStr, newStr, mode) {
    const oldLines = oldStr.split('\n');
    const newLines = newStr.split('\n');
    if (mode === 'new') {
        return newLines.map(line => {
            if (!oldLines.includes(line) && line !== '（削　除）') {
                return `<span class="diff-added">${escapeHtml(line)}</span>`;
            }
            return escapeHtml(line);
        }).join('\n');
    } else {
        return oldLines.map(line => {
            if (!newLines.includes(line) && line !== '（新　設）') {
                return `<span class="diff-removed">${escapeHtml(line)}</span>`;
            }
            return escapeHtml(line);
        }).join('\n');
    }
}

/**
 * 生成される整形済み JSON のプレビュー
 */
function renderCleanJsonView($container) {
    const cleanData = cleanDataForExport(AppState.data);
    const jsonStr = JSON.stringify(cleanData, null, 2);

    $container.append(`
        <div class="d-flex align-items-center justify-content-between mb-2">
            <span class="small fw-bold text-secondary">構文チェック済み JSON 出力プレビュー</span>
            <button type="button" class="btn btn-outline-primary btn-sm" id="btn-copy-json">
                <i class="ph ph-copy"></i> JSON全文をコピー
            </button>
        </div>
        <pre class="p-3 bg-dark text-light rounded-3 small font-monospace mb-0" style="max-height: calc(100vh - 11rem); overflow: auto;">${escapeHtml(jsonStr)}</pre>
    `);
}

// =============================================================
// 6. ヘルパー（エスケープ・連番振り直し・トースト）
// =============================================================
function escapeHtml(str) {
    return String(str || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

function escapeAttr(str) {
    return escapeHtml(str).replace(/"/g, '&quot;');
}

function autoResizeAllTextareas() {
    $('textarea.auto-resize').each(function () {
        this.style.height = 'auto';
        this.style.height = Math.max(42, this.scrollHeight + 2) + 'px';
    });
}

function showToast(message) {
    $('#toast-text').text(message);
    const toastEl = document.getElementById('editorToast');
    if (toastEl) {
        const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2400 });
        toast.show();
    }
}

/**
 * 全章・全節の条番号（枝番を除く本番号）を第1条から順番に振り直し、article_id も更新する
 */
function renumberAllArticles() {
    pushHistory();
    let counter = 1;
    (AppState.data.chapters || []).forEach(chap => {
        (chap.sections || []).forEach(sec => {
            (sec.articles || []).forEach(art => {
                const norm = toHalfWidthDigits(art.article_number || '');
                const subMatch = norm.match(/第\s*\d+\s*条\s*の\s*(\d+)/);
                if (subMatch) {
                    // 枝番の場合は直前の主番号を維持して枝番を付与
                    const mainNum = Math.max(1, counter - 1);
                    const subNum = parseInt(subMatch[1], 10);
                    art.article_number = formatArticleNumber(mainNum, subNum);
                    art.article_id = generateArticleIdFromNumber(art.article_number);
                } else {
                    art.article_number = formatArticleNumber(counter, null);
                    art.article_id = generateArticleIdFromNumber(art.article_number);
                    counter++;
                }
            });
        });
    });
    renderAll();
    showToast('全条文の条番号と article_id を連番で更新しました');
}

// =============================================================
// 7. イベントバインディング & 初期読み込み
// =============================================================
function loadJsonData(jsonObj, fileName) {
    AppState.data = deepClone(jsonObj);
    AppState.originalData = deepClone(jsonObj);
    AppState.currentFileName = fileName || '管理組合規約.json';
    AppState.selected = { cIdx: 0, sIdx: 0, aIdx: 0 };
    AppState.undoStack = [];
    AppState.redoStack = [];
    renderAll();
    showToast(`${AppState.currentFileName} を読み込みました`);
}

function loadPresetFile(relativePath, labelName) {
    $.getJSON(relativePath)
        .done(function (data) {
            loadJsonData(data, labelName);
        })
        .fail(function () {
            showToast(`${labelName} の自動読込に失敗しました。「JSON読込」ボタンからファイルを選択してください。`);
        });
}

$(document).ready(function () {
    // 初期表示: ./convt/管理組合規約.json を読み込む
    loadPresetFile('./convt/管理組合規約.json', '管理組合規約.json');

    // プリセット切替メニュー
    $(document).on('click', '.preset-load-item', function (e) {
        e.preventDefault();
        const path = $(this).data('path');
        const name = $(this).data('name');
        if (countModifiedArticles() > 0 && !confirm('編集中の変更があります。別のファイルを読み込んでよろしいですか？')) {
            return;
        }
        loadPresetFile(path, name);
    });

    // ローカルJSONファイル読込
    $('#file-input-json').on('change', function (e) {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = function (evt) {
            try {
                const parsed = JSON.parse(evt.target.result);
                if (!parsed || !Array.isArray(parsed.chapters)) {
                    alert('このJSONファイルには chapters 配列が含まれていません。');
                    return;
                }
                loadJsonData(parsed, file.name);
            } catch (err) {
                alert('JSONファイルの読み込みに失敗しました: ' + err.message);
            }
        };
        reader.readAsText(file, 'utf-8');
        $(this).val('');
    });

    // JSON保存（ダウンロード）
    $('#btn-download-json').on('click', function () {
        if (!AppState.data) return;
        const cleanData = cleanDataForExport(AppState.data);
        const jsonString = JSON.stringify(cleanData, null, 2) + '\n';
        const blob = new Blob([jsonString], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = AppState.currentFileName || '管理組合規約.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(`${a.download} を出力しました`);
    });

    // Undo / Redo
    $('#btn-undo').on('click', undo);
    $('#btn-redo').on('click', redo);
    $(document).on('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && !$(e.target).is('input, textarea')) {
            if (e.key.toLowerCase() === 'z' && !e.shiftKey) {
                e.preventDefault();
                undo();
            } else if (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey)) {
                e.preventDefault();
                redo();
            }
        }
    });

    // 全条番号の自動連番振り直し
    $('#btn-renumber-all-articles').on('click', function () {
        if (confirm('第1章から最終章まで、条番号（第１条、第２条…）と article_id を先頭から順番に振り直しますか？\n（※「第19条の２」のような枝番は維持されます）')) {
            renumberAllArticles();
        }
    });

    // 規約タイトル変更
    $('#bylaws-title-input').on('change', function () {
        pushHistory();
        AppState.data.bylaws_title = $(this).val();
        renderRightPane();
    });

    // 検索フィルタ
    $('#tree-search-input').on('input', function () {
        AppState.searchQuery = $(this).val();
        renderTreeSidebar();
    });
    $('#btn-clear-search').on('click', function () {
        $('#tree-search-input').val('');
        AppState.searchQuery = '';
        renderTreeSidebar();
    });

    // 左ツリーでの章・節・条の選択
    $(document).on('click', '.tree-article-item', function () {
        AppState.selected = {
            cIdx: Number($(this).data('cidx')),
            sIdx: Number($(this).data('sidx')),
            aIdx: Number($(this).data('aidx'))
        };
        renderAll();
    });
    $(document).on('click', '.tree-chapter-header', function () {
        const cIdx = Number($(this).data('cidx'));
        AppState.selected = { cIdx, sIdx: 0, aIdx: 0 };
        renderAll();
    });
    $(document).on('click', '.tree-section-header', function () {
        const cIdx = Number($(this).data('cidx'));
        const sIdx = Number($(this).data('sidx'));
        AppState.selected = { cIdx, sIdx, aIdx: 0 };
        renderAll();
    });

    // 右ペインタブ切替 & 幅拡大トグル
    $(document).on('click', '.preview-tab-btn', function () {
        AppState.previewTab = $(this).data('tab');
        renderRightPane();
    });
    $('#btn-expand-preview').on('click', function () {
        $('#preview-pane').toggleClass('expanded');
    });

    // JSON全文コピー
    $(document).on('click', '#btn-copy-json', function () {
        const cleanData = cleanDataForExport(AppState.data);
        navigator.clipboard.writeText(JSON.stringify(cleanData, null, 2) + '\n').then(() => {
            showToast('JSON全文をクリップボードにコピーしました');
        });
    });

    // -------------------------------------------------------------
    // 章・節の編集イベント
    // -------------------------------------------------------------
    $(document).on('change', '#inp-chapter-number', function () {
        pushHistory();
        AppState.data.chapters[AppState.selected.cIdx].chapter_number = $(this).val();
        renderTreeSidebar();
        renderRightPane();
    });
    $(document).on('change', '#inp-chapter-title', function () {
        pushHistory();
        AppState.data.chapters[AppState.selected.cIdx].chapter_title = $(this).val();
        renderTreeSidebar();
        renderRightPane();
    });
    $(document).on('change', '#chk-has-section', function () {
        pushHistory();
        const sec = AppState.data.chapters[AppState.selected.cIdx].sections[AppState.selected.sIdx];
        if ($(this).is(':checked')) {
            sec.section_number = sec.section_number || `第${toFullWidthDigits(AppState.selected.sIdx + 1)}節`;
            sec.section_title = sec.section_title || '新しい節';
        } else {
            sec.section_number = null;
            sec.section_title = null;
        }
        renderAll();
    });
    $(document).on('change', '#inp-section-number', function () {
        pushHistory();
        AppState.data.chapters[AppState.selected.cIdx].sections[AppState.selected.sIdx].section_number = $(this).val() || null;
        renderTreeSidebar();
        renderRightPane();
    });
    $(document).on('change', '#inp-section-title', function () {
        pushHistory();
        AppState.data.chapters[AppState.selected.cIdx].sections[AppState.selected.sIdx].section_title = $(this).val() || null;
        renderTreeSidebar();
        renderRightPane();
    });

    // 章の追加・削除
    $(document).on('click', '#btn-add-chapter', function () {
        pushHistory();
        const nextChapNum = AppState.data.chapters.length + 1;
        AppState.data.chapters.push({
            chapter_number: `第${toFullWidthDigits(nextChapNum)}章`,
            chapter_title: '新しい章',
            sections: [
                {
                    section_number: null,
                    section_title: null,
                    articles: [
                        {
                            article_id: 'art_9999',
                            article_number: '第99条',
                            title: '新規条文',
                            paragraphs: [{ paragraph_no: 1, text: '', items: [] }]
                        }
                    ]
                }
            ]
        });
        AppState.selected = { cIdx: AppState.data.chapters.length - 1, sIdx: 0, aIdx: 0 };
        renderAll();
        showToast('新しい章を追加しました');
    });

    $(document).on('click', '#btn-delete-chapter', function () {
        if (AppState.data.chapters.length <= 1) {
            alert('最後の1章は削除できません。');
            return;
        }
        const chap = AppState.data.chapters[AppState.selected.cIdx];
        if (!confirm(`「${chap.chapter_number} ${chap.chapter_title}」とその中の全条文を削除しますか？`)) return;
        pushHistory();
        AppState.data.chapters.splice(AppState.selected.cIdx, 1);
        clampSelection();
        renderAll();
        showToast('章を削除しました');
    });

    // 節の追加・削除
    $(document).on('click', '#btn-add-section', function () {
        pushHistory();
        const chap = AppState.data.chapters[AppState.selected.cIdx];
        // 既存の先頭節に節番号が無い場合は第１節を設定
        if (chap.sections.length === 1 && !chap.sections[0].section_number) {
            chap.sections[0].section_number = '第１節';
            chap.sections[0].section_title = chap.sections[0].section_title || '総則';
        }
        const nextSecNum = chap.sections.length + 1;
        chap.sections.push({
            section_number: `第${toFullWidthDigits(nextSecNum)}節`,
            section_title: '新しい節',
            articles: [
                {
                    article_id: 'art_9999',
                    article_number: '第99条',
                    title: '新規条文',
                    paragraphs: [{ paragraph_no: 1, text: '', items: [] }]
                }
            ]
        });
        AppState.selected.sIdx = chap.sections.length - 1;
        AppState.selected.aIdx = 0;
        renderAll();
        showToast('節を追加しました');
    });

    $(document).on('click', '#btn-delete-section', function () {
        const chap = AppState.data.chapters[AppState.selected.cIdx];
        if (chap.sections.length <= 1) return;
        if (!confirm('この節とその中の条文を削除しますか？')) return;
        pushHistory();
        chap.sections.splice(AppState.selected.sIdx, 1);
        clampSelection();
        renderAll();
        showToast('節を削除しました');
    });

    // -------------------------------------------------------------
    // 条 (Article) の編集・追加・移動・削除イベント
    // -------------------------------------------------------------
    function getCurrentSection() {
        return AppState.data.chapters[AppState.selected.cIdx].sections[AppState.selected.sIdx];
    }
    function getCurrentArticle() {
        const sec = getCurrentSection();
        return sec ? sec.articles[AppState.selected.aIdx] : null;
    }

    $(document).on('input', '#inp-article-number', function () {
        const art = getCurrentArticle();
        if (!art) return;
        art.article_number = $(this).val();
        art.article_id = generateArticleIdFromNumber(art.article_number);
        $('#inp-article-id').val(art.article_id);
        renderTreeSidebar();
        renderRightPane();
    });
    $(document).on('focus', '#inp-article-number, #inp-article-title, .inp-para-text, .inp-item-no, .inp-item-text, .inp-item-term, .inp-item-definition, .inp-subitem-no, .inp-subitem-text, .inp-detail-no, .inp-detail-text', function () {
        $(this).data('snapshot-before', JSON.stringify(AppState.data));
    });
    $(document).on('change', '#inp-article-number, #inp-article-title, .inp-para-text, .inp-item-no, .inp-item-text, .inp-item-term, .inp-item-definition, .inp-subitem-no, .inp-subitem-text, .inp-detail-no, .inp-detail-text', function () {
        const beforeStr = $(this).data('snapshot-before');
        if (beforeStr && beforeStr !== JSON.stringify(AppState.data)) {
            AppState.undoStack.push(JSON.parse(beforeStr));
            if (AppState.undoStack.length > AppState.maxHistory) AppState.undoStack.shift();
            AppState.redoStack = [];
            updateHistoryButtons();
            saveAutoBackup();
        }
    });

    $(document).on('input', '#inp-article-title', function () {
        const art = getCurrentArticle();
        if (!art) return;
        art.title = $(this).val();
        renderTreeSidebar();
        renderRightPane();
    });

    // 最初の条を追加
    $(document).on('click', '#btn-add-first-article', function () {
        pushHistory();
        const sec = getCurrentSection();
        sec.articles.push({
            article_id: 'art_0001',
            article_number: '第１条',
            title: '新規条文',
            paragraphs: [{ paragraph_no: 1, text: '', items: [] }]
        });
        AppState.selected.aIdx = 0;
        renderAll();
    });

    // 現在の条のすぐ下に新しい条を追加
    $(document).on('click', '#btn-insert-art-after', function () {
        pushHistory();
        const sec = getCurrentSection();
        const curArt = getCurrentArticle();
        const norm = toHalfWidthDigits(curArt ? curArt.article_number : '');
        const match = norm.match(/第\s*(\d+)\s*条/);
        const nextMainNum = match ? (parseInt(match[1], 10) + 1) : (sec.articles.length + 1);
        const newArtNum = formatArticleNumber(nextMainNum, null);

        const newArt = {
            article_id: generateArticleIdFromNumber(newArtNum),
            article_number: newArtNum,
            title: '',
            paragraphs: [{ paragraph_no: 1, text: '', items: [] }]
        };
        sec.articles.splice(AppState.selected.aIdx + 1, 0, newArt);
        AppState.selected.aIdx += 1;
        renderAll();
        showToast(`${newArtNum} を追加しました（必要に応じて上部の「条番号自動連番」を実行できます）`);
    });

    // 枝番（第○条の２）を追加
    $(document).on('click', '#btn-insert-branch-art', function () {
        pushHistory();
        const sec = getCurrentSection();
        const curArt = getCurrentArticle();
        const norm = toHalfWidthDigits(curArt ? curArt.article_number : '');
        const match = norm.match(/第\s*(\d+)\s*条(?:\s*の\s*(\d+))?/);
        const mainNum = match ? parseInt(match[1], 10) : 1;
        const nextSubNum = match && match[2] ? (parseInt(match[2], 10) + 1) : 2;
        const newArtNum = formatArticleNumber(mainNum, nextSubNum);

        const newArt = {
            article_id: generateArticleIdFromNumber(newArtNum),
            article_number: newArtNum,
            title: '',
            paragraphs: [{ paragraph_no: 1, text: '', items: [] }]
        };
        sec.articles.splice(AppState.selected.aIdx + 1, 0, newArt);
        AppState.selected.aIdx += 1;
        renderAll();
        showToast(`枝番「${newArtNum}」を追加しました`);
    });

    // 条の上下移動
    $(document).on('click', '#btn-move-art-up', function () {
        const sec = getCurrentSection();
        const idx = AppState.selected.aIdx;
        if (idx <= 0) return;
        pushHistory();
        const temp = sec.articles[idx - 1];
        sec.articles[idx - 1] = sec.articles[idx];
        sec.articles[idx] = temp;
        AppState.selected.aIdx = idx - 1;
        renderAll();
    });
    $(document).on('click', '#btn-move-art-down', function () {
        const sec = getCurrentSection();
        const idx = AppState.selected.aIdx;
        if (idx >= sec.articles.length - 1) return;
        pushHistory();
        const temp = sec.articles[idx + 1];
        sec.articles[idx + 1] = sec.articles[idx];
        sec.articles[idx] = temp;
        AppState.selected.aIdx = idx + 1;
        renderAll();
    });

    // 条の削除
    $(document).on('click', '#btn-delete-article', function () {
        const sec = getCurrentSection();
        const art = getCurrentArticle();
        if (!art) return;
        if (!confirm(`「${art.article_number}（${art.title || '見出しなし'}）」を削除してよろしいですか？`)) return;
        pushHistory();
        sec.articles.splice(AppState.selected.aIdx, 1);
        clampSelection();
        renderAll();
        showToast('条文を削除しました');
    });

    // -------------------------------------------------------------
    // 項 (Paragraph) の編集・追加・移動・削除
    // -------------------------------------------------------------
    function renumberParagraphs(art) {
        (art.paragraphs || []).forEach((p, idx) => {
            p.paragraph_no = idx + 1;
        });
    }

    $(document).on('input', '.inp-para-text', function () {
        const pIdx = Number($(this).data('pidx'));
        const art = getCurrentArticle();
        if (!art || !art.paragraphs[pIdx]) return;
        art.paragraphs[pIdx].text = $(this).val();
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight + 2) + 'px';
        renderTreeSidebar();
        renderRightPane();
    });

    $(document).on('click', '#btn-add-paragraph', function () {
        const art = getCurrentArticle();
        if (!art) return;
        pushHistory();
        const nextNo = (art.paragraphs || []).length + 1;
        art.paragraphs.push({
            paragraph_no: nextNo,
            text: '',
            items: []
        });
        renderAll();
        showToast(`第${nextNo}項を追加しました`);
    });

    $(document).on('click', '.btn-move-para-up', function () {
        const pIdx = Number($(this).data('pidx'));
        const art = getCurrentArticle();
        if (!art || pIdx <= 0) return;
        pushHistory();
        const tmp = art.paragraphs[pIdx - 1];
        art.paragraphs[pIdx - 1] = art.paragraphs[pIdx];
        art.paragraphs[pIdx] = tmp;
        renumberParagraphs(art);
        renderAll();
    });

    $(document).on('click', '.btn-move-para-down', function () {
        const pIdx = Number($(this).data('pidx'));
        const art = getCurrentArticle();
        if (!art || pIdx >= art.paragraphs.length - 1) return;
        pushHistory();
        const tmp = art.paragraphs[pIdx + 1];
        art.paragraphs[pIdx + 1] = art.paragraphs[pIdx];
        art.paragraphs[pIdx] = tmp;
        renumberParagraphs(art);
        renderAll();
    });

    $(document).on('click', '.btn-delete-para', function () {
        const pIdx = Number($(this).data('pidx'));
        const art = getCurrentArticle();
        if (!art || art.paragraphs.length <= 1) return;
        if (!confirm(`第${pIdx + 1}項を削除しますか？`)) return;
        pushHistory();
        art.paragraphs.splice(pIdx, 1);
        renumberParagraphs(art);
        renderAll();
        showToast('項を削除しました');
    });

    // -------------------------------------------------------------
    // 号 (Item) の編集・追加・移動・削除・用語定義モード切替
    // -------------------------------------------------------------
    $(document).on('click', '.btn-add-item', function () {
        const pIdx = Number($(this).data('pidx'));
        const art = getCurrentArticle();
        const para = art.paragraphs[pIdx];
        pushHistory();
        if (!Array.isArray(para.items)) para.items = [];
        const nextKanji = numberToKanji(para.items.length + 1);
        // 第2条（定義）の場合はデフォルトで用語・定義モードにする
        const isDefArt = art.title === '定義' || para.items.some(it => it.term !== undefined);
        if (isDefArt) {
            para.items.push({ item_no: nextKanji, term: '', definition: '', _isTermMode: true });
        } else {
            para.items.push({ item_no: nextKanji, text: '', _isTermMode: false });
        }
        renderAll();
        showToast(`第${pIdx + 1}項に「${nextKanji}」号を追加しました`);
    });

    $(document).on('click', '.btn-renumber-items', function () {
        const pIdx = Number($(this).data('pidx'));
        const para = getCurrentArticle().paragraphs[pIdx];
        pushHistory();
        (para.items || []).forEach((it, idx) => {
            it.item_no = numberToKanji(idx + 1);
        });
        renderAll();
        showToast('号番号を漢数字（一、二、三…）で振り直しました');
    });

    $(document).on('change', '.chk-item-term-mode', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const item = getCurrentArticle().paragraphs[pIdx].items[iIdx];
        pushHistory();
        const toTermMode = $(this).is(':checked');
        item._isTermMode = toTermMode;
        if (toTermMode) {
            item.term = item.term || '';
            item.definition = item.definition || item.text || '';
            delete item.text;
        } else {
            item.text = item.text || ((item.term ? item.term + ' ' : '') + (item.definition || ''));
            delete item.term;
            delete item.definition;
        }
        renderAll();
    });

    $(document).on('input', '.inp-item-no', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].item_no = $(this).val();
        renderRightPane();
    });
    $(document).on('input', '.inp-item-text', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].text = $(this).val();
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight + 2) + 'px';
        renderTreeSidebar();
        renderRightPane();
    });
    $(document).on('input', '.inp-item-term', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].term = $(this).val();
        renderTreeSidebar();
        renderRightPane();
    });
    $(document).on('input', '.inp-item-definition', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].definition = $(this).val();
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight + 2) + 'px';
        renderTreeSidebar();
        renderRightPane();
    });

    $(document).on('click', '.btn-move-item-up', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const items = getCurrentArticle().paragraphs[pIdx].items;
        if (iIdx <= 0) return;
        pushHistory();
        const tmp = items[iIdx - 1];
        items[iIdx - 1] = items[iIdx];
        items[iIdx] = tmp;
        items.forEach((it, idx) => { it.item_no = numberToKanji(idx + 1); });
        renderAll();
    });

    $(document).on('click', '.btn-move-item-down', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const items = getCurrentArticle().paragraphs[pIdx].items;
        if (iIdx >= items.length - 1) return;
        pushHistory();
        const tmp = items[iIdx + 1];
        items[iIdx + 1] = items[iIdx];
        items[iIdx] = tmp;
        items.forEach((it, idx) => { it.item_no = numberToKanji(idx + 1); });
        renderAll();
    });

    $(document).on('click', '.btn-delete-item', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const items = getCurrentArticle().paragraphs[pIdx].items;
        pushHistory();
        items.splice(iIdx, 1);
        items.forEach((it, idx) => { it.item_no = numberToKanji(idx + 1); });
        renderAll();
    });

    // -------------------------------------------------------------
    // 細目1 (sub_items: イ、ロ、ハ / ①、②) の編集・追加・移動・削除
    // -------------------------------------------------------------
    $(document).on('click', '.btn-add-subitem', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const item = getCurrentArticle().paragraphs[pIdx].items[iIdx];
        pushHistory();
        if (!Array.isArray(item.sub_items)) item.sub_items = [];
        const existingFirst = item.sub_items[0] ? item.sub_items[0].sub_item_no : '';
        const useCircle = CIRCLE_NUM_LIST.includes(existingFirst);
        const nextNo = useCircle
            ? (CIRCLE_NUM_LIST[item.sub_items.length] || `(${item.sub_items.length + 1})`)
            : (IROHA_LIST[item.sub_items.length] || '・');
        item.sub_items.push({
            sub_item_no: nextNo,
            text: ''
        });
        renderAll();
    });

    $(document).on('input', '.inp-subitem-no', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items[subIdx].sub_item_no = $(this).val();
        renderRightPane();
    });

    $(document).on('input', '.inp-subitem-text', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items[subIdx].text = $(this).val();
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight + 2) + 'px';
        renderTreeSidebar();
        renderRightPane();
    });

    $(document).on('click', '.btn-move-subitem-up', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const subs = getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items;
        if (subIdx <= 0) return;
        pushHistory();
        const tmp = subs[subIdx - 1];
        subs[subIdx - 1] = subs[subIdx];
        subs[subIdx] = tmp;
        renderAll();
    });

    $(document).on('click', '.btn-move-subitem-down', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const subs = getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items;
        if (subIdx >= subs.length - 1) return;
        pushHistory();
        const tmp = subs[subIdx + 1];
        subs[subIdx + 1] = subs[subIdx];
        subs[subIdx] = tmp;
        renderAll();
    });

    $(document).on('click', '.btn-delete-subitem', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const item = getCurrentArticle().paragraphs[pIdx].items[iIdx];
        pushHistory();
        item.sub_items.splice(subIdx, 1);
        if (item.sub_items.length === 0) delete item.sub_items;
        renderAll();
    });

    // -------------------------------------------------------------
    // 細目2 (details: （１）、（２）) の編集・追加・削除
    // -------------------------------------------------------------
    $(document).on('click', '.btn-add-detail', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const sub = getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items[subIdx];
        pushHistory();
        if (!Array.isArray(sub.details)) sub.details = [];
        const nextDetNo = `（${toFullWidthDigits(sub.details.length + 1)}）`;
        sub.details.push({
            detail_no: nextDetNo,
            text: ''
        });
        renderAll();
    });

    $(document).on('input', '.inp-detail-no', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const detIdx = Number($(this).data('detidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items[subIdx].details[detIdx].detail_no = $(this).val();
        renderRightPane();
    });

    $(document).on('input', '.inp-detail-text', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const detIdx = Number($(this).data('detidx'));
        getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items[subIdx].details[detIdx].text = $(this).val();
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight + 2) + 'px';
        renderTreeSidebar();
        renderRightPane();
    });

    $(document).on('click', '.btn-delete-detail', function () {
        const pIdx = Number($(this).data('pidx'));
        const iIdx = Number($(this).data('iidx'));
        const subIdx = Number($(this).data('subidx'));
        const detIdx = Number($(this).data('detidx'));
        const sub = getCurrentArticle().paragraphs[pIdx].items[iIdx].sub_items[subIdx];
        pushHistory();
        sub.details.splice(detIdx, 1);
        if (sub.details.length === 0) delete sub.details;
        renderAll();
    });
});
