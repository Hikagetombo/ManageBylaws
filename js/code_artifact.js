// -------------------------------------------------------------
// 1. 各要素を個別にスタイル・ブックマーク編集できる独立関数群
// -------------------------------------------------------------

/**
 * [章] のHTML構造・スタイル・ブックマークを編集する関数
 */
function renderChapter(chapter, chapterIndex) {
    const chapterId = `chapter-${chapterIndex + 1}`;
    const chapterNum = chapter.chapter_number || `第${chapterIndex + 1}章`;
    const chapterTitle = chapter.chapter_title || "";

    return $(`
    <section id="${chapterId}" class="chapter-card anchor-target shadow-sm mb-2">
        <div class="chapter-header px-4 py-3 d-flex align-items-center justify-content-between">
        <div class="d-flex align-items-center gap-3">
            <span class="badge chapter-num-badge px-2 py-1">
            ${chapterNum}
            </span>
            <h3 class="chapter-title-text">
            ${chapterTitle}
            </h3>
        </div>
        <a href="#${chapterId}" class="copy-anchor-btn" title="章のブックマークリンク" data-anchor="${chapterId}">
            <i class="ph ph-link-simple fs-5"></i>
        </a>
        </div>
        <div class="chapter-body p-3 p-sm-4 d-flex flex-column gap-4">
        <!-- 節または条文がここに入ります -->
        </div>
    </section>
    `);
}

/**
 * [節] のHTML構造・スタイル・ブックマークを編集する関数
 */
function renderSection(section, sectionIndex, chapterIndex) {
    const sectionId = `sec-${chapterIndex + 1}-${sectionIndex + 1}`;
    const sectionNum = section.section_number || `第${sectionIndex + 1}節`;
    const sectionTitle = section.section_title || "";

    // 節が存在しない場合は条文格納用コンテナのみ返す
    if (!section.section_title) {
    return $(`<div class="section-container d-flex flex-column gap-3"></div>`);
    }

    return $(`
    <div id="${sectionId}" class="section-container anchor-target pt-2 d-flex flex-column gap-3">
        <div class="section-header d-flex align-items-center gap-2 pb-2">
        <span class="badge section-num-badge px-2 py-1">
            ${sectionNum}
        </span>
        <h4 class="section-title-text">
            ${sectionTitle}
        </h4>
        <a href="#${sectionId}" class="copy-anchor-btn ms-auto" title="節のリンク" data-anchor="${sectionId}">
            <i class="ph ph-link-simple"></i>
        </a>
        </div>
        <div class="section-articles d-flex flex-column gap-3"></div>
    </div>
    `);
}

/**
 * [条] のHTML構造・スタイル・ブックマークを編集する関数
 * 条（article）には属性 id を設定
 */
function renderArticle(article, articleIndex) {
    const articleId = article.article_id || `art_${String(articleIndex + 1).padStart(4, '0')}`;
    const artTitle = article.title ? `（${article.title}）` : "";

    return $(`
    <article id="${articleId}" class="article-box anchor-target p-3 p-sm-4">
        <!-- 条の見出し（条のタイトルを上段に配置） -->
        <div class="article-header d-flex align-items-start justify-content-between gap-2 pb-2 mb-3">
        <div class="d-flex flex-wrap align-items-center gap-2">
            <span class="article-title-text">
            ${artTitle}
            </span>
        </div>
        <button type="button" class="copy-anchor-btn" title="この条のリンクをコピー" data-anchor="${articleId}">
            <i class="ph ph-bookmark-simple fs-5"></i>
        </button>
        </div>
        <!-- 項リストコンテナ -->
        <div class="paragraphs-list d-flex flex-column gap-3"></div>
    </article>
    `);
}

/**
 * [項] のHTML構造・スタイルを編集する関数
 * - 項（paragraph）には属性 id を設定
 * - 項の番号(paragraph_no) が 1 の場合は項番号を表示せず、条番号の横に全角1文字空けて配置
 */
function renderParagraph(paragraph, paraIndex, articleId, artNumber = "") {
    const paraNo = paragraph.paragraph_no !== undefined ? paragraph.paragraph_no : (paraIndex + 1);
    const paragraphId = paragraph.paragraph_id || `${articleId}_p${paraNo}`;

    // paragraph_no が 1 の場合は項番号バッジを表示せず、条番号＋全角1文字空白＋本文を表示
    const isFirstPara = Number(paraNo) === 1;
    const paraNoBadge = !isFirstPara
    ? `<span class="paragraph-no-badge">${paraNo}</span>`
    : ``;
    const textContent = isFirstPara && artNumber
    ? `<span class="article-num-text">${artNumber}</span>　${paragraph.text || ""}`
    : `${paragraph.text || ""}`;

    return $(`
    <div id="${paragraphId}" class="paragraph-item anchor-target d-flex flex-column gap-2">
        <div class="paragraph-main d-flex align-items-start gap-2">
        ${paraNoBadge}
        <p class="paragraph-text flex-grow-1">${textContent}</p>
        </div>
        <div class="items-list ps-3 ps-sm-4 d-flex flex-column gap-2"></div>
    </div>
    `);
}

/**
 * [号] のHTML構造・スタイルを編集する関数
 * - 号（item）には属性 id を設定
 * - 号の番号(item_no) は漢数字のみとし、「第一号」なら「一」のみ表示する
 */
function renderItem(item, itemIndex, paragraphId) {
    const itemId = item.item_id || `${paragraphId}_i${itemIndex + 1}`;
    // 「第一号」のような表記であっても「第」「号」を除いて漢数字のみ（「一」など）を表示
    const itemNoKanji = item.item_no
    ? String(item.item_no).replace(/^第/, "").replace(/号$/, "")
    : "";
    const termBadge = item.term
    ? `<span class="item-term-badge">【${item.term}】</span>`
    : "";
    const bodyText = item.text || item.definition || "";

    return $(`
    <div id="${itemId}" class="item-block anchor-target p-2 p-sm-3 d-flex flex-column gap-2">
        <div class="item-main d-flex align-items-start gap-2">
        <span class="item-no-badge">
            ${itemNoKanji || "・"}
        </span>
        <div class="item-body-text flex-grow-1">
            ${termBadge}${bodyText}
        </div>
        </div>
        <div class="sub-items-list ps-3 ps-sm-4 ms-2 mt-1 d-flex flex-column gap-2"></div>
    </div>
    `);
}

/**
 * [sub_items / details] （イ、ロ、(1)、(2)等）のHTML構造・スタイルを編集する関数
 */
function renderSubItem(subItem) {
    const subNo = subItem.sub_item_no ? `${subItem.sub_item_no}` : "・";
    const $sub = $(`
    <div class="sub-item-block d-flex flex-column gap-1">
        <div class="sub-item-main d-flex align-items-start gap-2">
        <span class="sub-item-no">${subNo}</span>
        <span class="sub-item-text">${subItem.text || ""}</span>
        </div>
        <div class="details-list ps-3 ms-1 d-flex flex-column gap-1"></div>
    </div>
    `);

    // details の追加
    if (Array.isArray(subItem.details) && subItem.details.length > 0) {
    subItem.details.forEach(detail => {
        $sub.find('.details-list').append(`
        <div class="detail-item d-flex align-items-start gap-1">
            <span class="detail-no">${detail.detail_no || ""}</span>
            <span class="detail-text">${detail.text || ""}</span>
        </div>
        `);
    });
    } else {
    $sub.find('.details-list').remove();
    }
    return $sub;
}

// -------------------------------------------------------------
// 2. メインのレンダリングコントローラー
// -------------------------------------------------------------
function renderBylaws(data) {
    // タイトル & カウンタ反映
    $('#bylaws-title').text(data.bylaws_title || "規約改正案");
    $('#top-title').text(data.bylaws_title || "規約ビューア");

    const $container = $('#articles-container').empty();
    const $toc = $('#toc-container').empty();

    let totalArticles = 0;
    let totalChapters = (data.chapters || []).length;

    // 章ループ
    (data.chapters || []).forEach((chapter, cIdx) => {
    const $chapter = renderChapter(chapter, cIdx);
    const $chapterBody = $chapter.find('.chapter-body');

    // 目次: 章ヘッダー
    const chapterId = `chapter-${cIdx + 1}`;
    $toc.append(`
        <div class="toc-chapter-item pt-2 pb-1">
        <a href="#${chapterId}" class="toc-chapter-link text-truncate">
            ${chapter.chapter_number || ""} ${chapter.chapter_title || ""}
        </a>
        </div>
    `);

    // 節ループ
    (chapter.sections || []).forEach((section, sIdx) => {
        const $section = renderSection(section, sIdx, cIdx);
        const $articlesTarget = section.section_title ? $section.find('.section-articles') : $section;

        // 条ループ
        (section.articles || []).forEach((article, aIdx) => {
        totalArticles++;
        const articleId = article.article_id || `art_${String(totalArticles).padStart(4, '0')}`;
        const artNumber = article.article_number || `第${aIdx + 1}条`;
        const $article = renderArticle({ ...article, article_id: articleId }, aIdx);
        const $paragraphsList = $article.find('.paragraphs-list');

        // 目次: 条アイテム
        $toc.append(`
            <a href="#${articleId}" class="toc-article-link text-truncate">
            <span class="toc-article-num">${article.article_number}</span>${article.title || ""}
            </a>
        `);

        // 項 (paragraphs) ループ
        (article.paragraphs || []).forEach((para, pIdx) => {
            const paraNo = para.paragraph_no !== undefined ? para.paragraph_no : (pIdx + 1);
            const paragraphId = para.paragraph_id || `${articleId}_p${paraNo}`;
            const $para = renderParagraph(para, pIdx, articleId, artNumber);
            const $itemsList = $para.find('.items-list');

            // 号 (items) ループ
            if (Array.isArray(para.items) && para.items.length > 0) {
            para.items.forEach((item, iIdx) => {
                const $item = renderItem(item, iIdx, paragraphId);
                const $subItemsList = $item.find('.sub-items-list');

                // sub_items ループ
                if (Array.isArray(item.sub_items) && item.sub_items.length > 0) {
                item.sub_items.forEach((sub) => {
                    const $sub = renderSubItem(sub);
                    $subItemsList.append($sub);
                });
                } else {
                $subItemsList.remove();
                }

                $itemsList.append($item);
            });
            } else {
            $itemsList.remove();
            }

            $paragraphsList.append($para);
        });

        $articlesTarget.append($article);
        });

        $chapterBody.append($section);
    });

    $container.append($chapter);
    });
}

// -------------------------------------------------------------
// 3. イベントハンドラー & トースト通知
// -------------------------------------------------------------
function showToast(text) {
    $('#toast-text').text(text);
    const toastEl = document.getElementById('copyToast');
    const toast = bootstrap.Toast.getOrCreateInstance(toastEl, { delay: 2500 });
    toast.show();
}

$(document).ready(function() {
    // 初期表示: 同じディレクトリの「管理組合規約.json」を読み込んで表示
    $.getJSON('./convt/管理組合規約.json')
    .done(function(data) {
        renderBylaws(data);
    })
    .fail(function(jqXHR, textStatus, errorThrown) {
        console.error('管理組合規約.json の読み込みに失敗しました:', textStatus, errorThrown);
        $('#bylaws-title').text('管理組合規約.json の読み込みに失敗しました');
        showToast('管理組合規約.json を読み込めませんでした');
    });

    // JSONファイルアップロードによる切り替え機能
    $('#json-file-input').on('change', function(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(evt) {
        try {
        const uploadedJson = JSON.parse(evt.target.result);
        renderBylaws(uploadedJson);
        showToast(`${file.name} を読み込みました`);
        } catch (err) {
        showToast("JSONの解析に失敗しました");
        console.error(err);
        }
    };
    reader.readAsText(file);
    });

    // ブックマークURLコピー機能
    $(document).on('click', '.copy-anchor-btn', function(e) {
    e.preventDefault();
    const anchorId = $(this).data('anchor');
    const url = `${window.location.origin}${window.location.pathname}#${anchorId}`;

    const $temp = $('<textarea>');
    $('body').append($temp);
    $temp.val(url).select();
    document.execCommand('copy');
    $temp.remove();

    showToast(`#${anchorId} のリンクをコピーしました`);
    });

    // 目次リンクをクリックしたときにモバイル用Offcanvasを閉じる
    $(document).on('click', '#toc-container a', function() {
    const offcanvasEl = document.getElementById('sidebarOffcanvas');
    const bsOffcanvas = bootstrap.Offcanvas.getInstance(offcanvasEl);
    if (bsOffcanvas) {
        bsOffcanvas.hide();
    }
    });
});
