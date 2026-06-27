/**
 * ═══════════════════════════════════════════════════════════════════
 * SESSION CHECK — Verificar sesión activa (VERSIÓN MEJORADA)
 * ═══════════════════════════════════════════════════════════════════
 * 
 * CAMBIOS:
 * - Solo redirige si recibe 401 (token expirado)
 * - Ignora timeouts y errores de red (permite continuar)
 * - Aumenta timeout a 10 segundos (conexión lenta)
 * - Verifica cada 10 minutos (no cada 5)
 * - Advertencias en console, sin logout forzado
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
    CHECK_INTERVAL: 10 * 60 * 1000,  // Cada 10 minutos (no cada 5)
    VERIFY_ENDPOINT: '/auth/verify',
    LOGIN_REDIRECT: '/login',
    TIMEOUT: 10000                    // 10 segundos (no 5)
  };

  // ════════════════════════════════════════════════════════════════
  // FUNCIONES
  // ════════════════════════════════════════════════════════════════

  /**
   * Verifica si la sesión está activa
   * 
   * IMPORTANTE:
   * - Solo redirige si recibe 401 (token expirado)
   * - Ignora timeouts y errores de red (continúa normalmente)
   * - Solo advierte en console
   * 
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

      // ✅ 401 = Token expiró → REDIRIGIR
      if (response.status === 401) {
        console.warn('⚠️ [SESSION] Token expirado (401). Redirigiendo a login...');
        redirectToLogin('sesion_expirada');
        return false;
      }

      // ✅ 200 OK = Sesión válida
      if (response.ok) {
        const data = await response.json();
        
        if (data.valid) {
          console.debug('✅ [SESSION] Sesión activa', {
            usuario_id: data.usuario_id,
            rol: data.rol,
            expires_at: data.expires_at
          });
          return true;
        } else {
          console.warn('⚠️ [SESSION] Sesión no válida según servidor');
          redirectToLogin('sesion_invalida');
          return false;
        }
      }

      // ✅ Otro status code = Advertir pero NO redirigir
      console.warn(`⚠️ [SESSION] Error verificando sesión (${response.status}). Continuando...`);
      return true;  // Permitir continuar

    } catch (error) {
      // ✅ TIMEOUT = Advertir pero NO redirigir (conexión lenta)
      if (error.name === 'AbortError') {
        console.warn('⚠️ [SESSION] Timeout verificando sesión (conexión lenta). Continuando...');
        return true;  // Permitir continuar
      }

      // ✅ ERROR DE RED = Advertir pero NO redirigir (offline posible)
      if (error instanceof TypeError && error.message.includes('fetch')) {
        console.warn('⚠️ [SESSION] Error de red. Posiblemente offline. Continuando...');
        return true;  // Permitir continuar
      }

      // ✅ Otro error = Advertir pero NO redirigir
      console.warn('⚠️ [SESSION] Error inesperado:', error.message, 'Continuando...');
      return true;  // Permitir continuar
    }
  }

  /**
   * Redirige a login con razón especificada
   * @param {string} razon - Razón del logout
   */
  function redirectToLogin(razon) {
    const url = new URL(CONFIG.LOGIN_REDIRECT, window.location.origin);
    url.searchParams.set('razon', razon);
    url.searchParams.set('from', window.location.pathname);
    
    console.warn(`🔄 [SESSION] Redirigiendo a login (razón: ${razon})`);
    
    // Redirigir con delay para asegurar que se ejecuta
    setTimeout(() => {
      window.location.href = url.toString();
    }, 500);
  }

  /**
   * Verifica sesión periódicamente (cada 10 minutos)
   */
  function startPeriodicCheck() {
    console.log('📋 [SESSION] Verificación automática iniciada (cada 10 minutos)');
    
    // NO verificar inmediatamente al cargar (evita redireccionamientos innecesarios)
    // Esperar 10 minutos para la primera verificación
    
    // Luego verificar periódicamente cada 10 minutos
    const intervalId = setInterval(() => {
      console.debug('🔄 [SESSION] Verificando estado de sesión...');
      checkSession();
    }, CONFIG.CHECK_INTERVAL);

    // Retornar el ID del intervalo para poder cancelarlo si es necesario
    return intervalId;
  }

  /**
   * Verifica sesión cuando la página vuelve del background
   * (muy útil para dispositivos móviles)
   */
  function onPageVisibilityChange() {
    document.addEventListener('visibilitychange', () => {
      if (!document.hidden) {
        console.debug('👁️ [SESSION] Página visible nuevamente. Verificando sesión...');
        checkSession();
      } else {
        console.debug('👁️ [SESSION] Página en background');
      }
    });
  }

  /**
   * Verifica sesión cuando se recupera del offline
   */
  function onOnlineOffline() {
    window.addEventListener('online', () => {
      console.log('📡 [SESSION] Conexión restaurada. Verificando sesión...');
      checkSession();
    });

    window.addEventListener('offline', () => {
      console.warn('⚠️ [SESSION] Sin conexión a internet. Continuando en modo offline...');
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

  // Exponer funciones globalmente para debugging
  window.sessionCheck = {
    check: checkSession,
    config: CONFIG,
    status: '✅ Cargado (verificación cada 10 minutos)'
  };

  console.log('✅ [SESSION] Session checker cargado');
  console.log('   Verificación cada 10 minutos');
  console.log('   Solo redirige si token expira (401)');
  console.log('   Tolera timeouts y errores de red');
  console.log('   Debug: window.sessionCheck');

})();