// /static/js/form-autosave.js
// Auto-guarda el formulario cada 15 segundos en localStorage
 
(function() {
  const STORAGE_KEY = 'inspeccionDraft';
  const SAVE_INTERVAL = 15000; // 15 segundos
  
  let form = null;
  let lastSaveTime = 0;
 
  // Esperar a que el DOM esté listo
  document.addEventListener('DOMContentLoaded', () => {
    form = document.getElementById('inspeccionForm');
    if (!form) return;
 
    // Restaurar datos guardados al cargar
    restoreFormData();
 
    // Auto-guardar cada 15 segundos
    setInterval(saveFormData, SAVE_INTERVAL);
 
    // Guardar al cambiar campos
    form.addEventListener('change', saveFormData);
    form.addEventListener('input', saveFormData);
 
    // Limpiar al enviar exitosamente
    form.addEventListener('submit', () => {
      setTimeout(() => {
        localStorage.removeItem(STORAGE_KEY);
      }, 1000);
    });
 
    // Limpiar al resetear
    form.addEventListener('reset', () => {
      localStorage.removeItem(STORAGE_KEY);
    });
  });
 
  // ==========================================
  // GUARDAR DATOS
  // ==========================================
  function saveFormData() {
    if (!form) return;
 
    const now = Date.now();
    if (now - lastSaveTime < 3000) return; // No guardar más de una vez cada 3s
 
    lastSaveTime = now;
 
    try {
      const formData = new FormData(form);
      const data = {};
 
      // Guardar cada campo
      formData.forEach((value, key) => {
        if (!data[key]) {
          data[key] = value;
        } else {
          if (!Array.isArray(data[key])) {
            data[key] = [data[key]];
          }
          data[key].push(value);
        }
      });
 
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      showSaveIndicator();
    } catch (err) {
      console.log('❌ Error guardando:', err);
    }
  }
 
  // ==========================================
  // RESTAURAR DATOS
  // ==========================================
  function restoreFormData() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (!saved) return;
 
      const data = JSON.parse(saved);
      let restored = false;
 
      // Restaurar cada campo
      Object.keys(data).forEach(key => {
        const fields = form.querySelectorAll(`[name="${key}"]`);
        
        if (fields.length > 0) {
          const field = fields[0];
          const value = data[key];
 
          if (field.type === 'radio' || field.type === 'checkbox') {
            form.querySelectorAll(`[name="${key}"]`).forEach(f => {
              f.checked = (f.value === value);
            });
          } else if (field.tagName === 'SELECT') {
            field.value = value;
          } else if (field.tagName === 'TEXTAREA') {
            field.value = value;
          } else {
            field.value = value;
          }
 
          restored = true;
        }
      });
 
      if (restored) {
        showNotification('✅ Datos restaurados del navegador');
      }
    } catch (err) {
      console.log('⚠️ Error restaurando:', err);
    }
  }
 
  // ==========================================
  // INDICADORES VISUALES
  // ==========================================
  function showSaveIndicator() {
    let indicator = document.getElementById('saveIndicator');
 
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'saveIndicator';
      indicator.style.cssText = `
        position: fixed;
        bottom: 30px;
        right: 30px;
        padding: 8px 12px;
        background: rgba(59, 130, 246, 0.85);
        color: white;
        border-radius: 6px;
        font-size: 11px;
        z-index: 999;
        opacity: 0;
        transition: opacity 0.3s;
      `;
      document.body.appendChild(indicator);
    }
 
    indicator.textContent = '💾 Guardando...';
    indicator.style.opacity = '1';
 
    setTimeout(() => {
      indicator.textContent = '✅ Guardado';
      setTimeout(() => {
        indicator.style.opacity = '0';
      }, 1500);
    }, 500);
  }
 
  function showNotification(msg) {
    const div = document.createElement('div');
    div.style.cssText = `
      position: fixed;
      top: 90px;
      left: 20px;
      padding: 10px 15px;
      background: rgba(34, 197, 94, 0.9);
      color: white;
      border-radius: 6px;
      font-size: 12px;
      z-index: 1000;
    `;
    div.textContent = msg;
    document.body.appendChild(div);
 
    setTimeout(() => {
      div.style.opacity = '0';
      setTimeout(() => div.remove(), 300);
    }, 3000);
  }
})();