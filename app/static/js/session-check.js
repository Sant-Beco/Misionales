/**
 * ═══════════════════════════════════════════════════════════════════
 * SESSION CHECK — Verificar sesión activa cada 5 minutos
 * ═══════════════════════════════════════════════════════════════════
 * 
 * Previene logout inesperado verificando periódicamente que la sesión
 * sigue activa. Si el token expiró, redirige a login automáticamente.
 * 
 * INSTALACIÓN:
 *   1. Copiar este archivo a: app/static/js/session-check.js
 *   2. Agregar a templates: <script src="/static/js/session-check.js"></script>
 *   3. Reiniciar FastAPI
 */

(function() {
  'use strict';

  // ════════════════════════════════════════════════════════════════
  // CONFIGURACIÓN
  // ════════════════════════════════════════════════════════════════

  const CONFIG = {
    CHECK_INTERVAL: 5 * 60 * 1000,  // Cada 5 minutos
    VERIFY_ENDPOINT: '/auth/verify',
    LOGIN_REDIRECT: '/login',
    TIMEOUT: 5000                    // 5 segundos timeout
  };

  // ════════════════════════════════════════════════════════════════
  // FUNCIONES
  // ════════════════════════════════════════════════════════════════

  /**
   * Verifica si la sesión está activa
   * @returns {Promise<boolean>} true si sesión activa, false si expiró
   */
  async function checkSession() {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), CONFIG.TIMEOUT);

      const response = await fetch(CONFIG.VERIFY_ENDPOINT, {
        method: 'GET',
        credentials: 'include',  // ✅ Incluir cookie
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (response.status === 401) {
        // Token expiró
        console.warn('⚠️ Sesión expirada. Token no válido.');
        redirectToLogin('sesion_expirada');
        return false;
      }

      if (!response.ok) {
        console.error('❌ Error verificando sesión:', response.status);
        return false;
      }

      const data = await response.json();
      
      if (data.valid) {
        console.debug('✅ Sesión activa:', {
          usuario_id: data.usuario_id,
          rol: data.rol,
          expires_at: data.expires_at
        });
        return true;
      } else {
        console.warn('⚠️ Sesión no válida según servidor');
        redirectToLogin('sesion_invalida');
        return false;
      }

    } catch (error) {
      if (error.name === 'AbortError') {
        console.warn('⚠️ Timeout verificando sesión');
        return false;
      }

      console.error('❌ Error en checkSession:', error.message);
      
      // Si hay error de red, asumir que está offline
      if (error instanceof TypeError && error.message.includes('fetch')) {
        console.warn('📡 Error de red, posiblemente offline');
        return true;  // Permitir continuar offline
      }

      return false;
    }
  }

  /**
   * Redirige a login con razón especificada
   * @param {string} razon - Razón del logout (sesion_expirada, sesion_invalida, etc)
   */
  function redirectToLogin(razon) {
    const url = new URL(CONFIG.LOGIN_REDIRECT, window.location.origin);
    url.searchParams.set('razon', razon);
    url.searchParams.set('from', window.location.pathname);
    
    console.warn(`🔄 Redirigiendo a login (razón: ${razon})`);
    
    // Redirigir con un pequeño delay para asegurar que se ejecuta
    setTimeout(() => {
      window.location.href = url.toString();
    }, 500);
  }

  /**
   * Verifica sesión periódicamente
   */
  function startPeriodicCheck() {
    console.log('📋 Verificación de sesión iniciada (cada 5 minutos)');
    
    // Verificar inmediatamente al cargar
    checkSession();
    
    // Luego verificar periódicamente
    setInterval(() => {
      console.debug('🔄 Verificando sesión...');
      checkSession();
    }, CONFIG.CHECK_INTERVAL);
  }

  /**
   * Verifica sesión cuando la página vuelve del background
   */
  function onPageVisibilityChange() {
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        console.debug('👁️ Página visible, verificando sesión...');
        checkSession();
      }
    });
  }

  /**
   * Verifica sesión cuando se recupera del offline
   */
  function onOnlineOffline() {
    window.addEventListener('online', () => {
      console.log('📡 Conexión restaurada, verificando sesión...');
      checkSession();
    });

    window.addEventListener('offline', () => {
      console.warn('⚠️ Sin conexión a internet');
    });
  }

  // ════════════════════════════════════════════════════════════════
  // INICIALIZACIÓN
  // ════════════════════════════════════════════════════════════════

  // Ejecutar cuando el documento está listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      startPeriodicCheck();
      onPageVisibilityChange();
      onOnlineOffline();
    });
  } else {
    // Ya está cargado
    startPeriodicCheck();
    onPageVisibilityChange();
    onOnlineOffline();
  }

  // Exponer funciones globalmente para acceso desde console/debugging
  window.sessionCheck = {
    check: checkSession,
    config: CONFIG
  };

  console.log('✅ Session checker cargado. Acceso: window.sessionCheck.check()');

})();