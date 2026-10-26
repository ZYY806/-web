/* ============================================================
   德州文旅网站 前端交互脚本 main.js
   ============================================================ */

// 灯箱：点击卡片图片看大图
function openLightbox(src) {
    document.getElementById('lightbox-img').src = src;
    document.getElementById('lightbox').classList.add('show');
}

function closeLightbox() {
    document.getElementById('lightbox').classList.remove('show');
}

// 给所有 .zoomable 图片绑定点击放大
document.addEventListener('DOMContentLoaded', function () {
    var imgs = document.querySelectorAll('.zoomable');
    imgs.forEach(function (img) {
        img.style.cursor = 'zoom-in';
        img.addEventListener('click', function () {
            openLightbox(img.src);
        });
    });

    // flash 提示 3 秒后自动消失
    setTimeout(function () {
        var flashes = document.querySelectorAll('.flashes li');
        flashes.forEach(function (li) {
            li.style.transition = 'opacity .4s';
            li.style.opacity = '0';
            setTimeout(function () { li.remove(); }, 400);
        });
    }, 3000);
});
