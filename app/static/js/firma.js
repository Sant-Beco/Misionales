// app/static/js/firma.js
(function(){
  const canvas = document.getElementById('firmaCanvas');
  const ctx = canvas.getContext('2d');
  let drawing = false;
  let last = { x: 0, y: 0 };

  function resizeCanvas() {
    // Mantener tamaño CSS vs canvas pixels
    const style = getComputedStyle(canvas);
    const w = canvas.clientWidth;
    canvas.width = w * (window.devicePixelRatio || 1);
    canvas.height = 200 * (window.devicePixelRatio || 1);
    ctx.scale(window.devicePixelRatio || 1, window.devicePixelRatio || 1);
    ctx.lineWidth = 2;
    ctx.lineCap = 'round';
  }
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  function getPos(e) {
    if (e.touches && e.touches.length > 0) {
      const rect = canvas.getBoundingClientRect();
      return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
    } else {
      const rect = canvas.getBoundingClientRect();
      return { x: e.clientX - rect.left, y: e.clientY - rect.top };
    }
  }

  canvas.addEventListener('mousedown', function(e){
    drawing = true; last = getPos(e);
  });
  canvas.addEventListener('touchstart', function(e){ drawing = true; last = getPos(e); e.preventDefault(); });

  canvas.addEventListener('mousemove', function(e){
    if (!drawing) return;
    const p = getPos(e);
    ctx.beginPath();
    ctx.moveTo(last.x, last.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    last = p;
  });
  canvas.addEventListener('touchmove', function(e){ if (!drawing) return; const p = getPos(e); ctx.beginPath(); ctx.moveTo(last.x,last.y); ctx.lineTo(p.x,p.y); ctx.stroke(); last = p; e.preventDefault(); });

  document.addEventListener('mouseup', function(){ drawing = false; });
  document.addEventListener('touchend', function(){ drawing = false; });

  document.getElementById('limpiarBtn').addEventListener('click', function(){
    ctx.clearRect(0,0,canvas.width,canvas.height);
  });

  window.firmaApp = {
    getDataURL: function(){
      // devolver dataURL en tamaño razonable
      return canvas.toDataURL('image/png');
    }
  };

  document.getElementById('guardarBtn').addEventListener('click', function(){
    const data = window.firmaApp.getDataURL();
    const img = document.createElement('img');
    img.src = data;
    img.style.maxWidth = '300px';
    const preview = document.getElementById('firmaPreview');
    preview.innerHTML = '';
    preview.appendChild(img);
  });
})();
