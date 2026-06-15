(() => {
    const SETTINGS = {
    "charset": "standard",
    "customCharset": " .:-=+*#%@",
    "brailleVariant": "standard",
    "fontSize": 10,
    "hoverStrength": 13,
    "mouseInteractionMode": "attract",
    "mouseAreaSize": 180,
    "mouseSpread": 1,
    "charSpacing": 1,
    "renderFont": "\"Helvetica Neue\", Helvetica, Arial, sans-serif",
    "outputAspect": "source",
    "contrast": 1,
    "brightness": 0,
    "opacity": 1,
    "vignette": 0,
    "borderGlow": 0,
    "bgDither": 0,
    "inverseDither": 0,
    "invert": false,
    "ditherType": "floyd-steinberg",
    "ditherStrength": 0.8,
    "style": "dotcross",
    "halftoneShape": "circle",
    "halftoneSize": 1,
    "halftoneRotation": 0,
    "colorMode": "color",
    "terminalCharset": "binary",
    "retroDuotone": "amber-classic",
    "retroNoise": 0.45,
    "backgroundColor": "#000000",
    "customColor": "#00ff99",
    "particleDensity": 0.5,
    "particleChar": "*",
    "letterSet": "alphabet",
    "claudeDensity": 0.7,
    "lineLength": 1,
    "lineWidth": 1,
    "lineThickness": 1.6,
    "lineRotation": 0,
    "overlayPreset": "noise",
    "overlayStrength": 0.45,
    "noiseScale": 24,
    "noiseSpeed": 1,
    "noiseDirection": "left",
    "intervalSpacing": 12,
    "intervalSpeed": 1,
    "intervalWidth": 2,
    "intervalDirection": "down",
    "beamDirection": "right",
    "glitchDirection": "right",
    "crtDirection": "down",
    "matrixDirection": "down",
    "matrixScale": 18,
    "matrixSpeed": 1,
    "webglLayerEnabled": true,
    "webglOverlayType": "ambient-starfield",
    "webglOverlayPosition": "behind",
    "webglOverlayAffectsAscii": false,
    "webglOverlayOpacity": 1,
    "webglOverlayIntensity": 0.45,
    "webglOverlayLineSpread": 0.25,
    "webglOverlayPulseSpeed": 1,
    "webglOverlayLightning": 1,
    "webglOverlayMouseInfluence": 1,
    "webglOverlayGrain": 0.02,
    "webglOverlayColor": "#f5ff99",
    "themeOutputInvert": false
  };
    const EXPORT_OPTIONS = {"enableInteractionEffects":true,"transparentBackground":true,"enableAlphaMask":true,"alphaMaskEnd":85,"enableFadeIn":true,"fadeInDurationMs":900,"pauseWhenOffscreen":true,"adaptivePerformance":true,"maxFps":30,"idleFps":12,"visibilityThreshold":0.01,"reportFps":false,"enableWatermark":false,"watermarkText":"Made in ASC11"};
    const SOURCE = {
    "type": "image",
    "url": "data:image/jpeg;base64,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"
  };
    const IS_TRANSPARENT_BG = Boolean(EXPORT_OPTIONS.transparentBackground);
    const WATERMARK_LABEL = String(EXPORT_OPTIONS.watermarkText || "Made in ASC11");
  
    const CHARSETS = {"standard":" .:-=+*#%@","blocks":" ░▒▓█","detailed":" .'`^\",:;Il!i><~+_-?][}{1)(|\\\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$","minimal":" ·░█","binary":" 01","letters-alphabet":"ABCDEFGHIJKLMNOPQRSTUVWXYZ","letters-lowercase":"abcdefghijklmnopqrstuvwxyz","letters-mixed":"AaBbCcDdEeFfGgHhIiJjKkLlMmNnOoPpQqRrSsTtUuVvWwXxYyZz","letters-symbols":"@#$%&*+=-<>~","braille":" ⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿"};
    const BRAILLE_VARIANTS = {"standard":" ⠁⠂⠃⠄⠅⠆⠇⠈⠉⠊⠋⠌⠍⠎⠏⠐⠑⠒⠓⠔⠕⠖⠗⠘⠙⠚⠛⠜⠝⠞⠟⠠⠡⠢⠣⠤⠥⠦⠧⠨⠩⠪⠫⠬⠭⠮⠯⠰⠱⠲⠳⠴⠵⠶⠷⠸⠹⠺⠻⠼⠽⠾⠿","sparse":" ⠁⠂⠄⠈⠐⠠⡀⢀⣀⣿","dense":" ⠃⠇⠏⠟⠿"};
    const MATRIX_CHARS = " アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン";
    const HALFTONE_CHARS = " .,:;irsXA253hMHGS#9B&@";
    const RETRO_CHARS = "o";
    const TERMINAL_CHARSET_PRESETS = {"binary":" 010101","brackets":" []/\\<>","symbols":" $_+","mixed":" 01[]/\\<>$_+|","matrix":" 01{}[]/\\<>|_+-"};
    const RETRO_DUOTONE_PALETTES = {"amber-classic":{"low":{"r":20,"g":12,"b":6},"high":{"r":255,"g":223,"b":178}},"cyan-night":{"low":{"r":6,"g":16,"b":22},"high":{"r":166,"g":240,"b":255}},"violet-haze":{"low":{"r":17,"g":10,"b":26},"high":{"r":242,"g":198,"b":255}},"lime-pulse":{"low":{"r":10,"g":18,"b":8},"high":{"r":226,"g":255,"b":162}},"mono-ice":{"low":{"r":12,"g":12,"b":12},"high":{"r":245,"g":248,"b":255}}};
    const HOVER_ATTRACT_RADIUS = 180;
    const CLICK_BURST_RADIUS = 340;
    const CLICK_BURST_STRENGTH = 56;
    const CLICK_BURST_DURATION_MS = 640;
    const FPS_MESSAGE_TYPE = "ascii-dither-template-fps";
    const IS_TEMPLATE_PREVIEW_RUNTIME = EXPORT_OPTIONS.reportFps === true;
    const TEMPLATE_PREVIEW_RUNTIME_KEY = '__asciiTemplatePreviewRuntime__';
    const runtimeScope = typeof window !== 'undefined' ? window : globalThis;
    const previewRuntimeId = IS_TEMPLATE_PREVIEW_RUNTIME ? String(Date.now()) + '-' + Math.random().toString(36).slice(2) : '';
    const SHOULD_REPORT_FPS =
      EXPORT_OPTIONS.reportFps === true &&
      typeof window.parent !== 'undefined' &&
      window.parent !== window;
  
    if (IS_TEMPLATE_PREVIEW_RUNTIME) {
      const existingRuntime = runtimeScope[TEMPLATE_PREVIEW_RUNTIME_KEY];
      if (existingRuntime && typeof existingRuntime.destroy === 'function') {
        try {
          existingRuntime.destroy();
        } catch {
          // Ignore stale runtime destroy errors.
        }
      }
      runtimeScope[TEMPLATE_PREVIEW_RUNTIME_KEY] = { id: previewRuntimeId, destroy: null };
    }
  
    const mount = document.querySelector('[data-ascii-dither-bg]');
    if (!mount) return;
  
    if (typeof mount.__asciiDitherDestroy === 'function') {
      mount.__asciiDitherDestroy();
    }
  
    mount.style.position = 'absolute';
    mount.style.inset = '';
    mount.style.top = '0';
    mount.style.left = '0';
    mount.style.right = '0';
    mount.style.bottom = 'auto';
    mount.style.height = '100vh';
    mount.style.zIndex = '0';
    mount.style.pointerEvents = 'none';
    mount.style.overflow = 'hidden';
    mount.style.background = 'transparent';
    const fadeInDurationMs = Math.max(0, Number(EXPORT_OPTIONS.fadeInDurationMs ?? 900) || 900);
    if (EXPORT_OPTIONS.enableFadeIn === true && fadeInDurationMs > 0) {
      mount.style.opacity = '0';
      mount.style.transition = 'opacity ' + fadeInDurationMs + 'ms ease';
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          mount.style.opacity = '1';
        });
      });
    } else {
      mount.style.opacity = '1';
      mount.style.removeProperty('transition');
    }
  
    const parent = mount.parentElement;
    if (parent && window.getComputedStyle(parent).position === 'static') {
      parent.style.position = 'relative';
    }
  
    const backgroundLayer = document.createElement('div');
    Object.assign(backgroundLayer.style, {
      position: 'absolute',
      inset: '0',
      pointerEvents: 'none',
      zIndex: '0',
      background: IS_TRANSPARENT_BG ? 'transparent' : (SETTINGS.backgroundColor || '#000000')
    });
  
    const canvas = document.createElement('canvas');
    Object.assign(canvas.style, {
      position: 'absolute',
      top: '50%',
      left: '50%',
      width: 'auto',
      height: 'auto',
      maxWidth: '100%',
      maxHeight: '100%',
      transform: 'translate(-50%, -50%)',
      display: 'block',
      zIndex: '2'
    });
  
    const webglCanvas = document.createElement('canvas');
    Object.assign(webglCanvas.style, {
      position: 'absolute',
      top: '50%',
      left: '50%',
      width: 'auto',
      height: 'auto',
      maxWidth: '100%',
      maxHeight: '100%',
      transform: 'translate(-50%, -50%)',
      display: 'none',
      opacity: '0',
      zIndex: '1',
      pointerEvents: 'none'
    });
    const webglShaderCanvas = document.createElement('canvas');
    Object.assign(webglShaderCanvas.style, {
      position: 'absolute',
      top: '50%',
      left: '50%',
      width: 'auto',
      height: 'auto',
      maxWidth: '100%',
      maxHeight: '100%',
      transform: 'translate(-50%, -50%)',
      display: 'none',
      opacity: '0',
      zIndex: '1',
      pointerEvents: 'none'
    });
    const legacyAlphaMaskStop = Math.max(0, Math.min(100, Number(EXPORT_OPTIONS.alphaMaskStop ?? 85) || 85));
    const alphaMaskEndRaw = Number(EXPORT_OPTIONS.alphaMaskEnd ?? legacyAlphaMaskStop);
    const alphaMaskEnd = Math.max(0, Math.min(100, Number.isFinite(alphaMaskEndRaw) ? alphaMaskEndRaw : legacyAlphaMaskStop));
    if (EXPORT_OPTIONS.enableAlphaMask !== false) {
      const alphaMaskValue =
        'linear-gradient(to bottom, black 0%, black ' + alphaMaskEnd + '%, transparent 100%)';
      mount.setAttribute('data-alpha-mask', 'bottom-' + alphaMaskEnd);
      canvas.style.setProperty('mask-image', alphaMaskValue);
      canvas.style.setProperty('-webkit-mask-image', alphaMaskValue);
      webglCanvas.style.setProperty('mask-image', alphaMaskValue);
      webglCanvas.style.setProperty('-webkit-mask-image', alphaMaskValue);
      webglShaderCanvas.style.setProperty('mask-image', alphaMaskValue);
      webglShaderCanvas.style.setProperty('-webkit-mask-image', alphaMaskValue);
    } else {
      mount.removeAttribute('data-alpha-mask');
      canvas.style.removeProperty('mask-image');
      canvas.style.removeProperty('-webkit-mask-image');
      webglCanvas.style.removeProperty('mask-image');
      webglCanvas.style.removeProperty('-webkit-mask-image');
      webglShaderCanvas.style.removeProperty('mask-image');
      webglShaderCanvas.style.removeProperty('-webkit-mask-image');
    }
  
    let watermarkLayer = null;
    if (EXPORT_OPTIONS.enableWatermark === true) {
      watermarkLayer = document.createElement('div');
      Object.assign(watermarkLayer.style, {
        position: 'absolute',
        right: '14px',
        bottom: '12px',
        zIndex: '4',
        pointerEvents: 'none',
        userSelect: 'none',
        font: '600 12px "Helvetica Neue", Helvetica, Arial, sans-serif',
        letterSpacing: '0.03em',
        color: 'rgba(255, 255, 255, 0.92)',
        padding: '4px 8px',
        borderRadius: '999px',
        border: '1px solid rgba(255, 255, 255, 0.24)',
        background: 'rgba(0, 0, 0, 0.5)',
        textShadow: '0 1px 1px rgba(0, 0, 0, 0.45)',
      });
      watermarkLayer.textContent = WATERMARK_LABEL;
    }
  
    if (watermarkLayer) {
      mount.replaceChildren(backgroundLayer, webglCanvas, webglShaderCanvas, canvas, watermarkLayer);
    } else {
      mount.replaceChildren(backgroundLayer, webglCanvas, webglShaderCanvas, canvas);
    }
  
    const ctx = canvas.getContext('2d');
    const webglCtx = webglCanvas.getContext('2d');
    const webglShaderGl =
      webglShaderCanvas.getContext('webgl', { alpha: true, premultipliedAlpha: false }) ||
      webglShaderCanvas.getContext('experimental-webgl', { alpha: true, premultipliedAlpha: false });
    const sampleCanvas = document.createElement('canvas');
    const sampleCtx = sampleCanvas.getContext('2d', { willReadFrequently: true });
    const webglSampleCanvas = document.createElement('canvas');
    const webglSampleCtx = webglSampleCanvas.getContext('2d', { willReadFrequently: true });
    if (!ctx || !webglCtx || !sampleCtx || !webglSampleCtx) throw new Error('Could not create canvas context');
  
    let source = null;
    let stream = null;
    let sourceLoopHandler = null;
    let rafId = null;
    let webglRafId = null;
    let intersectionObserver = null;
    let resizeObserver = null;
    let bounds = { left: 0, top: 0, width: 1, height: 1 };
    let viewWidth = 1;
    let viewHeight = 1;
    let renderWidth = 1;
    let renderHeight = 1;
    let pointer = { inside: false, x: 0, y: 0 };
    let clickBursts = [];
    let matrixRainState = { laneCount: 0, primaryCount: 0, speeds: [], phases: [], lengths: [] };
    let isInViewport = true;
    let isPageVisible = document.visibilityState !== 'hidden';
    let pendingForceRender = false;
    let lastRenderTime = 0;
    let fpsFrameCount = 0;
    let fpsWindowStart = 0;
    let lastReportedSignature = '';
    let lastFrameDurationMs = 0;
    let lastCharCount = 0;
    let webglScene = null;
    let webglStartTime = performance.now();
    let webglMouseState = null;
    let webglShaderResources = null;
  
    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }
  
    function reportFps(value, details = {}) {
      if (!SHOULD_REPORT_FPS) return;
      const normalized = Math.max(0, Math.round(Number(value) || 0));
      const normalizedChars = Math.max(0, Math.round(Number(details.chars) || 0));
      const normalizedFrameMs = Math.max(0, Math.round((Number(details.frameMs) || 0) * 10) / 10);
      const signature = normalized + '|' + normalizedChars + '|' + normalizedFrameMs;
      if (signature === lastReportedSignature) return;
      lastReportedSignature = signature;
      try {
        window.parent.postMessage(
          {
            type: FPS_MESSAGE_TYPE,
            fps: normalized,
            chars: normalizedChars,
            frameMs: normalizedFrameMs,
            instanceId: previewRuntimeId,
          },
          '*'
        );
      } catch {
        // Ignore cross-frame postMessage errors.
      }
    }
  
    function getDirectionVector(direction) {
      switch (direction) {
        case 'up':
          return { dx: 0, dy: -1 };
        case 'down':
          return { dx: 0, dy: 1 };
        case 'left':
          return { dx: -1, dy: 0 };
        case 'top-left':
          return { dx: -Math.SQRT1_2, dy: -Math.SQRT1_2 };
        case 'top-right':
          return { dx: Math.SQRT1_2, dy: -Math.SQRT1_2 };
        case 'bottom-left':
          return { dx: -Math.SQRT1_2, dy: Math.SQRT1_2 };
        case 'bottom-right':
          return { dx: Math.SQRT1_2, dy: Math.SQRT1_2 };
        case 'right':
        default:
          return { dx: 1, dy: 0 };
      }
    }
  
    function getDirectionProjection(direction) {
      const { dx, dy } = getDirectionVector(direction);
      const perpX = -dy;
      const perpY = dx;
      const primaryMin = (dx < 0 ? dx : 0) + (dy < 0 ? dy : 0);
      const primaryMax = (dx > 0 ? dx : 0) + (dy > 0 ? dy : 0);
      const secondaryMin = (perpX < 0 ? perpX : 0) + (perpY < 0 ? perpY : 0);
      const secondaryMax = (perpX > 0 ? perpX : 0) + (perpY > 0 ? perpY : 0);
      return {
        dx,
        dy,
        perpX,
        perpY,
        primaryMin,
        primarySpan: Math.max(0.0001, primaryMax - primaryMin),
        secondaryMin,
        secondarySpan: Math.max(0.0001, secondaryMax - secondaryMin),
      };
    }
  
    function projectDirection(x, y, cols, rows, projection) {
      const xNorm = x / Math.max(cols - 1, 1);
      const yNorm = y / Math.max(rows - 1, 1);
      const primaryRaw = xNorm * projection.dx + yNorm * projection.dy;
      const secondaryRaw = xNorm * projection.perpX + yNorm * projection.perpY;
      const primaryNorm = clamp((primaryRaw - projection.primaryMin) / projection.primarySpan, 0, 1);
      const secondaryNorm = clamp((secondaryRaw - projection.secondaryMin) / projection.secondarySpan, 0, 1);
      return { primaryNorm, secondaryNorm };
    }
  
    function applyTone(gray) {
      let value = gray;
      value = (value - 128) * SETTINGS.contrast + 128;
      value += SETTINGS.brightness * 2;
      value = clamp(value, 0, 255);
      if (SETTINGS.invert) value = 255 - value;
      return value;
    }
  
    function bayerThreshold(x, y) {
      const matrix = [
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5]
      ];
      return matrix[y % 4][x % 4] / 16;
    }
  
    function drawRegularPolygon(ctx, centerX, centerY, radius, sides, rotation) {
      if (!ctx || !Number.isFinite(radius) || radius <= 0 || sides < 3) return;
      const baseRotation = Number.isFinite(rotation) ? rotation : -Math.PI / 2;
      for (let i = 0; i < sides; i += 1) {
        const angle = baseRotation + (i / sides) * Math.PI * 2;
        const px = centerX + Math.cos(angle) * radius;
        const py = centerY + Math.sin(angle) * radius;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.closePath();
    }
  
    function drawHalftoneShape(ctx, shape, centerX, centerY, radius, rotationDeg = 0) {
      if (!ctx || radius <= 0) return;
      const rotation = ((Number(rotationDeg) || 0) * Math.PI) / 180;
      switch (shape) {
        case 'square': {
          const side = radius * 2;
          if (Math.abs(rotation) <= 0.0001) {
            ctx.fillRect(centerX - radius, centerY - radius, side, side);
            return;
          }
          ctx.save();
          ctx.translate(centerX, centerY);
          ctx.rotate(rotation);
          ctx.fillRect(-radius, -radius, side, side);
          ctx.restore();
          return;
        }
        case 'diamond':
          ctx.save();
          ctx.translate(centerX, centerY);
          ctx.rotate(rotation);
          ctx.beginPath();
          drawRegularPolygon(ctx, 0, 0, radius, 4, Math.PI / 4);
          ctx.fill();
          ctx.restore();
          return;
        case 'pentagon':
          ctx.save();
          ctx.translate(centerX, centerY);
          ctx.rotate(rotation);
          ctx.beginPath();
          drawRegularPolygon(ctx, 0, 0, radius, 5, -Math.PI / 2);
          ctx.fill();
          ctx.restore();
          return;
        case 'hexagon':
          ctx.save();
          ctx.translate(centerX, centerY);
          ctx.rotate(rotation);
          ctx.beginPath();
          drawRegularPolygon(ctx, 0, 0, radius, 6, -Math.PI / 2);
          ctx.fill();
          ctx.restore();
          return;
        case 'circle':
        default:
          ctx.beginPath();
          ctx.arc(centerX, centerY, radius, 0, Math.PI * 2);
          ctx.fill();
      }
    }
  
    function shouldApplyInverseDither(gray, x, y, strength, timeSeconds) {
      const amount = clamp(Number(strength ?? 0) || 0, 0, 3);
      if (amount <= 0) return 0;
      const tone = clamp(gray / 255, 0, 1);
      const threshold = bayerThreshold(x, y);
      const drift = (Math.sin((x + 1) * 7.31 + (y + 1) * 3.17 + timeSeconds * 0.75) + 1) * 0.5;
      const pattern = threshold * 0.72 + drift * 0.28;
      const transitioned = clamp((tone - 0.5) * (0.65 + amount * 1.95) + 0.5, 0, 1);
      const edge = transitioned - pattern;
      const softness = 1.1 + amount * 2.2;
      return clamp(edge * softness, 0, 1);
    }
  
    function invertCssColor(color) {
      const rgbMatch =
        /rgba?\(\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d*(?:\.\d+)?))?/i.exec(
          String(color || '')
        );
      if (rgbMatch) {
        const r = clamp(Math.round(Number(rgbMatch[1]) || 0), 0, 255);
        const g = clamp(Math.round(Number(rgbMatch[2]) || 0), 0, 255);
        const b = clamp(Math.round(Number(rgbMatch[3]) || 0), 0, 255);
        const alphaRaw = rgbMatch[4];
        if (alphaRaw != null && alphaRaw !== '') {
          const alpha = clamp(Number(alphaRaw) || 0, 0, 1);
          return 'rgba(' + (255 - r) + ', ' + (255 - g) + ', ' + (255 - b) + ', ' + alpha + ')';
        }
        return 'rgb(' + (255 - r) + ', ' + (255 - g) + ', ' + (255 - b) + ')';
      }
      const hexMatch = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(color || '').trim());
      if (hexMatch) {
        const hex =
          hexMatch[1].length === 3
            ? hexMatch[1].split('').map((char) => char + char).join('')
            : hexMatch[1];
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        return 'rgb(' + (255 - r) + ', ' + (255 - g) + ', ' + (255 - b) + ')';
      }
      return 'rgb(255, 255, 255)';
    }
  
    function parseCssColor(color) {
      const rgbMatch =
        /rgba?\(\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)\s*[, ]\s*(\d+(?:\.\d+)?)(?:\s*[,/]\s*(\d*(?:\.\d+)?))?/i.exec(
          String(color || '')
        );
      if (rgbMatch) {
        return {
          r: clamp(Math.round(Number(rgbMatch[1]) || 0), 0, 255),
          g: clamp(Math.round(Number(rgbMatch[2]) || 0), 0, 255),
          b: clamp(Math.round(Number(rgbMatch[3]) || 0), 0, 255),
          a: rgbMatch[4] != null && rgbMatch[4] !== '' ? clamp(Number(rgbMatch[4]) || 0, 0, 1) : 1,
        };
      }
  
      const hexMatch = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(String(color || '').trim());
      if (hexMatch) {
        const hex =
          hexMatch[1].length === 3
            ? hexMatch[1].split('').map((char) => char + char).join('')
            : hexMatch[1];
        return {
          r: parseInt(hex.slice(0, 2), 16),
          g: parseInt(hex.slice(2, 4), 16),
          b: parseInt(hex.slice(4, 6), 16),
          a: 1,
        };
      }
  
      return null;
    }
  
    function formatCssColor(color) {
      const red = clamp(Math.round(Number(color?.r) || 0), 0, 255);
      const green = clamp(Math.round(Number(color?.g) || 0), 0, 255);
      const blue = clamp(Math.round(Number(color?.b) || 0), 0, 255);
      const alpha = clamp(Number(color?.a ?? 1) || 0, 0, 1);
      if (alpha < 0.999) return 'rgba(' + red + ', ' + green + ', ' + blue + ', ' + alpha + ')';
      return 'rgb(' + red + ', ' + green + ', ' + blue + ')';
    }
  
    function rgbToHsv(r, g, b) {
      const red = clamp((Number(r) || 0) / 255, 0, 1);
      const green = clamp((Number(g) || 0) / 255, 0, 1);
      const blue = clamp((Number(b) || 0) / 255, 0, 1);
      const max = Math.max(red, green, blue);
      const min = Math.min(red, green, blue);
      const delta = max - min;
      let hue = 0;
  
      if (delta > 0.000001) {
        if (max === red) hue = ((green - blue) / delta) % 6;
        else if (max === green) hue = (blue - red) / delta + 2;
        else hue = (red - green) / delta + 4;
        hue *= 60;
        if (hue < 0) hue += 360;
      }
  
      return {
        h: hue,
        s: max <= 0 ? 0 : delta / max,
        v: max,
      };
    }
  
    function hsvToRgb(h, s, v) {
      const hue = ((Number(h) || 0) % 360 + 360) % 360;
      const sat = clamp(Number(s) || 0, 0, 1);
      const value = clamp(Number(v) || 0, 0, 1);
      const chroma = value * sat;
      const segment = hue / 60;
      const x = chroma * (1 - Math.abs((segment % 2) - 1));
      let red = 0;
      let green = 0;
      let blue = 0;
  
      if (segment >= 0 && segment < 1) {
        red = chroma;
        green = x;
      } else if (segment < 2) {
        red = x;
        green = chroma;
      } else if (segment < 3) {
        green = chroma;
        blue = x;
      } else if (segment < 4) {
        green = x;
        blue = chroma;
      } else if (segment < 5) {
        red = x;
        blue = chroma;
      } else {
        red = chroma;
        blue = x;
      }
  
      const match = value - chroma;
      return {
        r: Math.round((red + match) * 255),
        g: Math.round((green + match) * 255),
        b: Math.round((blue + match) * 255),
      };
    }
  
    function preserveHueAgainstLightBackground(color) {
      const parsed = parseCssColor(color);
      if (!parsed) return invertCssColor(color);
  
      const { r, g, b, a } = parsed;
      const maxChannel = Math.max(r, g, b);
      const minChannel = Math.min(r, g, b);
      const saturation = maxChannel <= 0 ? 0 : (maxChannel - minChannel) / maxChannel;
      if (saturation < 0.06) {
        return formatCssColor({ r: 255 - r, g: 255 - g, b: 255 - b, a });
      }
  
      const hsv = rgbToHsv(r, g, b);
      const luminance = clamp((0.299 * r + 0.587 * g + 0.114 * b) / 255, 0, 1);
      const remappedValue = clamp(Math.pow(1 - luminance, 1.2), 0, 1);
      const remappedSaturation = clamp(hsv.s * 1.08 + 0.04, 0, 1);
      return formatCssColor({
        ...hsvToRgb(hsv.h, remappedSaturation, remappedValue),
        a,
      });
    }
  
    function applyOutputPolarity(color, localInvert = false) {
      const shouldInvert = Boolean(SETTINGS.themeOutputInvert) !== Boolean(localInvert);
      if (!shouldInvert) return color;
      return preserveHueAgainstLightBackground(color);
    }
  
    function lerpChannel(from, to, amount) {
      return clamp(Math.round(from + (to - from) * amount), 0, 255);
    }
  
    const WEBGL_DEFAULT_MOUSE_X = -1000;
    const WEBGL_DEFAULT_MOUSE_Y = -1000;
    const WEBGL_MOUSE_IDLE_MS = 150;
    const WEBGL_MOUSE_FADE_MS = 350;
    webglMouseState = { x: WEBGL_DEFAULT_MOUSE_X, y: WEBGL_DEFAULT_MOUSE_Y, lastMove: -1e9, active: 0 };
    (function initAsciiWebglOverlayShared(globalScope) {
    const WEBGL_OVERLAY_TYPES = [
      'lightning-rails',
      'atmospheric-folds',
      'network-dome',
      'ambient-starfield',
      'terrain-mesh',
      'topology-dots',
      'radial-burst',
    ];
    const WEBGL_DEFAULT_MOUSE_X = -1000;
    const WEBGL_DEFAULT_MOUSE_Y = -1000;
    const WEBGL_OVERLAY_VERTEX_SHADER = `
  attribute vec2 aVertexPosition;
  void main() {
    gl_Position = vec4(aVertexPosition, 0.0, 1.0);
  }
  `;
    const WEBGL_OVERLAY_FRAGMENT_SHADER = `
  #ifdef GL_FRAGMENT_PRECISION_HIGH
  precision highp float;
  #else
  precision mediump float;
  #endif
  uniform vec2 u_resolution;
  uniform float u_time;
  uniform vec2 u_mouse;
  uniform float u_mouseActive;
  uniform float u_lineSpread;
  uniform float u_intensity;
  uniform float u_lightning;
  uniform float u_pulse;
  uniform float u_mouseInfluence;
  uniform float u_grain;
  uniform vec3 u_tint;
  
  float hash(float n) {
    return fract(sin(n) * 753.5453123);
  }
  
  float noise(float x) {
    float i = floor(x);
    float f = fract(x);
    f = f * f * (3.0 - 2.0 * f);
    return mix(hash(i), hash(i + 1.0), f);
  }
  
  float lightning(vec2 uv, vec2 a, vec2 b, float t) {
    vec2 ab = b - a;
    float len = length(ab);
    if (len < 0.01) return 0.0;
  
    vec2 dir = ab / len;
    vec2 pa = uv - a;
    float h = clamp(dot(pa, dir) / len, 0.0, 1.0);
    float dist = length(pa - dir * (h * len));
    float env = sin(h * 3.14159265);
  
    float offset = (noise(h * 15.0 - t * 20.0) - 0.5) * 0.1 * env;
    offset += (noise(h * 40.0 + t * 30.0) - 0.5) * 0.03 * env;
    float d = abs(dist + offset);
  
    return (0.0003 / (d + 0.0003) + 0.00002 / (d * d + 0.00002)) * env;
  }
  
  float pulseBand(float distanceToRail, float y, float t, float speed, float offset, float strength) {
    float pulseY = fract(t * speed + offset) * 4.0 - 2.0;
    return smoothstep(0.4, 0.0, abs(y - pulseY)) * strength / (distanceToRail + 0.002);
  }
  
  float wave(float y, float t, float offset, float amplitude) {
    return sin(y * 10.0 + t * 2.0 + offset) * amplitude;
  }
  
  void main() {
    vec2 safeResolution = max(u_resolution.xy, vec2(1.0));
    vec2 uv = gl_FragCoord.xy / safeResolution;
    uv = uv * 2.0 - 1.0;
    uv.x *= safeResolution.x / safeResolution.y;
  
    vec2 mouseUV = u_mouse / safeResolution;
    mouseUV = mouseUV * 2.0 - 1.0;
    mouseUV.x *= safeResolution.x / safeResolution.y;
  
    float spreadMix = clamp((u_lineSpread - 0.1) / 0.45, 0.0, 1.0);
    float spread = mix(0.12, 0.2, spreadMix);
    float pulseSpeed = max(0.1, u_pulse);
    float intensity = clamp(u_intensity, 0.0, 1.0);
    float lightningAmount = clamp(u_lightning, 0.0, 1.8);
    float mouseInfluence = clamp(u_mouseInfluence, 0.0, 2.0);
    float grainAmount = clamp(u_grain, 0.0, 0.12);
    float t = u_time * 0.5;
    float outerOffset = spread + mix(0.016, 0.028, spreadMix);
    float waveAmplitude = (0.004 + lightningAmount * 0.0015) * (0.85 + spreadMix * 0.25);
  
    float d1 = abs(uv.x - (-spread));
    float d2 = abs(uv.x - 0.0);
    float d3 = abs(uv.x - spread);
  
    float baseIntensity = mix(0.003, 0.0065, intensity);
    float glow = baseIntensity / (d1 + 0.002);
    glow += baseIntensity / (d2 + 0.002);
    glow += baseIntensity / (d3 + 0.002);
  
    glow += pulseBand(d1, uv.y, t, 0.2 * pulseSpeed, 0.0, 0.018 + intensity * 0.016) * 1.2;
    glow += pulseBand(d2, uv.y, t, 0.25 * pulseSpeed, 0.3, 0.018 + intensity * 0.016) * 1.2;
    glow += pulseBand(d3, uv.y, t, 0.15 * pulseSpeed, 0.7, 0.018 + intensity * 0.016) * 1.2;
  
    float wD1a = abs(uv.x - (-outerOffset + wave(uv.y, t, 0.0, waveAmplitude)));
    float wD1b = abs(uv.x - (-(spread - 0.02) + wave(uv.y, t, 1.0, waveAmplitude)));
    float wD2a = abs(uv.x - (-0.02 + wave(uv.y, t, 2.0, waveAmplitude)));
    float wD2b = abs(uv.x - ( 0.02 + wave(uv.y, t, 3.0, waveAmplitude)));
    float wD3a = abs(uv.x - ((spread - 0.02) + wave(uv.y, t, 4.0, waveAmplitude)));
    float wD3b = abs(uv.x - (outerOffset + wave(uv.y, t, 5.0, waveAmplitude)));
  
    float wavePulseStrength = (0.003 + intensity * 0.005) * (0.35 + lightningAmount * 0.2);
    glow += pulseBand(wD1a, uv.y, t, 0.3 * pulseSpeed, 0.1, wavePulseStrength);
    glow += pulseBand(wD1b, uv.y, t, 0.22 * pulseSpeed, 0.6, wavePulseStrength);
    glow += pulseBand(wD2a, uv.y, t, 0.28 * pulseSpeed, 0.2, wavePulseStrength);
    glow += pulseBand(wD2b, uv.y, t, 0.32 * pulseSpeed, 0.8, wavePulseStrength);
    glow += pulseBand(wD3a, uv.y, t, 0.35 * pulseSpeed, 0.4, wavePulseStrength);
    glow += pulseBand(wD3b, uv.y, t, 0.25 * pulseSpeed, 0.9, wavePulseStrength);
  
    vec2 p1 = vec2(-spread, mouseUV.y);
    vec2 p2 = vec2(0.0, mouseUV.y);
    vec2 p3 = vec2(spread, mouseUV.y);
  
    float flickerGate = step(0.15, noise(t * (40.0 + pulseSpeed * 12.0)));
    float flicker = flickerGate * (noise(t * (100.0 + pulseSpeed * 20.0)) * 0.7 + 0.3);
    float mouseActivation = clamp(u_mouseActive, 0.0, 1.0) * mouseInfluence;
    float mouseRadius = mix(1.4, 2.7, clamp(mouseInfluence * 0.5, 0.0, 1.0));
  
    glow += lightning(uv, p1, mouseUV, t) * smoothstep(mouseRadius, 0.0, length(mouseUV - p1)) * mouseActivation * flicker * lightningAmount;
    glow += lightning(uv, p2, mouseUV, t + 10.0) * smoothstep(mouseRadius, 0.0, length(mouseUV - p2)) * mouseActivation * flicker * lightningAmount;
    glow += lightning(uv, p3, mouseUV, t + 20.0) * smoothstep(mouseRadius, 0.0, length(mouseUV - p3)) * mouseActivation * flicker * lightningAmount;
  
    float distToCenter = length(uv);
    glow += (0.014 + intensity * 0.03) / (distToCenter + 0.02);
  
    vec3 tintColor = max(u_tint, vec3(0.06));
    vec3 railColor = mix(tintColor * 0.55, tintColor * 1.15, 0.72);
    vec3 highlightColor = mix(tintColor, vec3(1.0), 0.2 + intensity * 0.18);
    float shimmer = 0.8 + 0.2 * sin(t * (1.5 + pulseSpeed * 0.15) - distToCenter * 5.0);
    float falloff = 1.0 - smoothstep(0.3, 2.2, distToCenter);
  
    vec3 finalColor = railColor * glow * shimmer;
    finalColor += highlightColor * pow(max(glow, 0.0), 1.28) * (0.05 + lightningAmount * 0.02);
    finalColor *= falloff;
    float n = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);
    finalColor += (n - 0.5) * grainAmount * 0.32;
    finalColor = max(finalColor, vec3(0.0));
  
    float luminance = dot(finalColor, vec3(0.2126, 0.7152, 0.0722));
    float alpha = clamp(luminance * (1.2 + intensity * 1.4), 0.0, 0.98);
    gl_FragColor = vec4(finalColor, alpha);
  }
  `;
  
    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }
  
    function lerpChannel(from, to, amount) {
      return clamp(Math.round(from + (to - from) * amount), 0, 255);
    }
  
    function parseHexColor(value, fallback) {
      const fallbackColor = fallback || { r: 153, g: 187, b: 255 };
      if (typeof value !== 'string') return fallbackColor;
      const trimmed = value.trim();
      const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(trimmed);
      if (!match) return fallbackColor;
      const hex =
        match[1].length === 3
          ? match[1].split('').map((char) => char + char).join('')
          : match[1];
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16),
      };
    }
  
    function createShader(gl, type, source) {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    }
  
    function createWebglProgram(gl, vertexSource, fragmentSource) {
      const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource);
      const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
      if (!vertexShader || !fragmentShader) {
        if (vertexShader) gl.deleteShader(vertexShader);
        if (fragmentShader) gl.deleteShader(fragmentShader);
        return null;
      }
      const program = gl.createProgram();
      if (!program) {
        gl.deleteShader(vertexShader);
        gl.deleteShader(fragmentShader);
        return null;
      }
      gl.attachShader(program, vertexShader);
      gl.attachShader(program, fragmentShader);
      gl.linkProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        gl.deleteProgram(program);
        return null;
      }
      return program;
    }
  
    function rgbaColor(color, alpha) {
      return 'rgba(' + color.r + ', ' + color.g + ', ' + color.b + ', ' + clamp(alpha, 0, 1) + ')';
    }
  
    function mixColor(colorA, colorB, amount) {
      return {
        r: lerpChannel(colorA.r, colorB.r, amount),
        g: lerpChannel(colorA.g, colorB.g, amount),
        b: lerpChannel(colorA.b, colorB.b, amount),
      };
    }
  
    function scaleColor(color, factor) {
      return {
        r: clamp(Math.round(color.r * factor), 0, 255),
        g: clamp(Math.round(color.g * factor), 0, 255),
        b: clamp(Math.round(color.b * factor), 0, 255),
      };
    }
  
    function getWebglOverlayType(value) {
      switch (String(value || '').trim()) {
        case 'atmospheric-folds':
        case 'network-dome':
        case 'ambient-starfield':
        case 'terrain-mesh':
        case 'topology-dots':
        case 'radial-burst':
          return String(value).trim();
        default:
          return 'lightning-rails';
      }
    }
  
    function isCanvasOverlayType(overlayType) {
      return getWebglOverlayType(overlayType) !== 'lightning-rails';
    }
  
    function getWebglOverlayFragmentSource() {
      return WEBGL_OVERLAY_FRAGMENT_SHADER;
    }
  
    function getWebglOverlayUniformValues(settings) {
      const tint = parseHexColor(settings?.webglOverlayColor, { r: 153, g: 187, b: 255 });
      return {
        overlayType: getWebglOverlayType(settings?.webglOverlayType),
        opacity: clamp(Number(settings?.webglOverlayOpacity ?? 1) || 0, 0, 1),
        intensity: clamp(Number(settings?.webglOverlayIntensity ?? 0.45) || 0, 0, 1),
        lineSpread: clamp(Number(settings?.webglOverlayLineSpread ?? 0.25) || 0, 0.1, 0.55),
        pulseSpeed: clamp(Number(settings?.webglOverlayPulseSpeed ?? 1) || 0, 0.2, 4),
        lightning: 1,
        mouseInfluence: clamp(Number(settings?.webglOverlayMouseInfluence ?? 1) || 0, 0, 2),
        grain: clamp(Number(settings?.webglOverlayGrain ?? 0.02) || 0, 0, 0.12),
        tint,
        tintR: clamp(tint.r / 255, 0, 1),
        tintG: clamp(tint.g / 255, 0, 1),
        tintB: clamp(tint.b / 255, 0, 1),
      };
    }
  
    function ensureWebglOverlayResources(gl, fragmentSource = WEBGL_OVERLAY_FRAGMENT_SHADER) {
      if (!gl) return null;
      const program = createWebglProgram(gl, WEBGL_OVERLAY_VERTEX_SHADER, fragmentSource);
      if (!program) return null;
      const attribLocation = gl.getAttribLocation(program, 'aVertexPosition');
      if (attribLocation < 0) {
        gl.deleteProgram(program);
        return null;
      }
      const buffer = gl.createBuffer();
      if (!buffer) {
        gl.deleteProgram(program);
        return null;
      }
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([1, 1, -1, 1, 1, -1, -1, -1]), gl.STATIC_DRAW);
      return {
        program,
        attribLocation,
        buffer,
        uniforms: {
          resolution: gl.getUniformLocation(program, 'u_resolution'),
          time: gl.getUniformLocation(program, 'u_time'),
          mouse: gl.getUniformLocation(program, 'u_mouse'),
          mouseActive: gl.getUniformLocation(program, 'u_mouseActive'),
          lineSpread: gl.getUniformLocation(program, 'u_lineSpread'),
          intensity: gl.getUniformLocation(program, 'u_intensity'),
          lightning: gl.getUniformLocation(program, 'u_lightning'),
          pulse: gl.getUniformLocation(program, 'u_pulse'),
          mouseInfluence: gl.getUniformLocation(program, 'u_mouseInfluence'),
          grain: gl.getUniformLocation(program, 'u_grain'),
          tint: gl.getUniformLocation(program, 'u_tint'),
        },
      };
    }
  
    function disposeWebglOverlayResources(gl, resources) {
      if (!gl || !resources) return;
      gl.bindBuffer(gl.ARRAY_BUFFER, null);
      gl.useProgram(null);
      if (resources.buffer) gl.deleteBuffer(resources.buffer);
      if (resources.program) gl.deleteProgram(resources.program);
    }
  
    function renderShaderOverlayFrame(gl, resources, viewportWidth, viewportHeight, now, startTime, mouseState, uniformValues) {
      if (!gl || !resources || viewportWidth <= 0 || viewportHeight <= 0) return;
      gl.viewport(0, 0, viewportWidth, viewportHeight);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.useProgram(resources.program);
      gl.bindBuffer(gl.ARRAY_BUFFER, resources.buffer);
      gl.enableVertexAttribArray(resources.attribLocation);
      gl.vertexAttribPointer(resources.attribLocation, 2, gl.FLOAT, false, 0, 0);
      gl.disable(gl.DEPTH_TEST);
      gl.disable(gl.CULL_FACE);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  
      gl.uniform2f(resources.uniforms.resolution, viewportWidth, viewportHeight);
      gl.uniform1f(resources.uniforms.time, Math.max(0, now - startTime) * 0.001);
      gl.uniform2f(
        resources.uniforms.mouse,
        mouseState?.x ?? WEBGL_DEFAULT_MOUSE_X,
        viewportHeight - (mouseState?.y ?? WEBGL_DEFAULT_MOUSE_Y)
      );
      gl.uniform1f(resources.uniforms.mouseActive, clamp(mouseState?.active ?? 0, 0, 1));
      gl.uniform1f(resources.uniforms.lineSpread, uniformValues.lineSpread);
      gl.uniform1f(resources.uniforms.intensity, uniformValues.intensity);
      gl.uniform1f(resources.uniforms.lightning, uniformValues.lightning);
      gl.uniform1f(resources.uniforms.pulse, uniformValues.pulseSpeed);
      gl.uniform1f(resources.uniforms.mouseInfluence, uniformValues.mouseInfluence);
      gl.uniform1f(resources.uniforms.grain, uniformValues.grain);
      gl.uniform3f(resources.uniforms.tint, uniformValues.tintR, uniformValues.tintG, uniformValues.tintB);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    }
  
    function updateScenePointer(state, mouseState, width, height, smoothing) {
      if (!state) return;
      const hasMouse =
        Number.isFinite(mouseState?.x) &&
        Number.isFinite(mouseState?.y) &&
        mouseState.x > WEBGL_DEFAULT_MOUSE_X * 0.5 &&
        mouseState.y > WEBGL_DEFAULT_MOUSE_Y * 0.5;
      const mouseNormX = hasMouse ? (mouseState.x / Math.max(width, 1) - 0.5) * 2 : 0;
      const mouseNormY = hasMouse ? (mouseState.y / Math.max(height, 1) - 0.5) * 2 : 0;
      const amount = clamp(Number(smoothing) || 0.04, 0.01, 0.2);
      state.pointerX += (mouseNormX - state.pointerX) * amount;
      state.pointerY += (mouseNormY - state.pointerY) * amount;
    }
  
    function drawGlow(ctx, x, y, radius, color, alpha, verticalScale) {
      const scaleY = Math.max(0.2, Number(verticalScale) || 1);
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(1, scaleY);
      const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
      gradient.addColorStop(0, rgbaColor(color, alpha));
      gradient.addColorStop(0.45, rgbaColor(scaleColor(color, 0.78), alpha * 0.42));
      gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  
    function drawGrain(ctx, width, height, nowSeconds, amount, color) {
      if (amount <= 0.002) return;
      const count = Math.round(24 + amount * 220);
      ctx.save();
      ctx.globalCompositeOperation = 'overlay';
      ctx.fillStyle = rgbaColor(color, 0.018 + amount * 0.08);
      for (let index = 0; index < count; index += 1) {
        const seed = index * 12.713 + nowSeconds * 2.3;
        const gx = ((Math.sin(seed) * 43758.5453) % 1 + 1) % 1;
        const gy = ((Math.sin(seed * 1.67) * 24634.6345) % 1 + 1) % 1;
        ctx.fillRect(Math.floor(gx * width), Math.floor(gy * height), 1, 1);
      }
      ctx.restore();
    }
  
    function createCanvasOverlaySceneState(overlayType) {
      const normalizedType = getWebglOverlayType(overlayType);
      if (normalizedType === 'network-dome') {
        return {
          type: normalizedType,
          value: {
            pointerX: 0,
            pointerY: 0,
            lines: Array.from({ length: 72 }, (_, index) => ({
              offset: index / 72,
              speed: 0.35 + Math.random() * 0.65,
              particles: [Math.random(), Math.random(), Math.random()],
            })),
          },
        };
      }
      if (normalizedType === 'ambient-starfield') {
        return {
          type: normalizedType,
          value: {
            pointerX: 0,
            pointerY: 0,
            stars: Array.from({ length: 520 }, () => ({
              x: (Math.random() - 0.5) * 2,
              y: (Math.random() - 0.5) * 2,
              z: Math.random(),
              twinkle: Math.random() * Math.PI * 2,
              speed: 0.45 + Math.random() * 0.8,
              size: 0.6 + Math.random() * 1.25,
            })),
          },
        };
      }
      if (normalizedType === 'terrain-mesh') {
        return { type: normalizedType, value: { pointerX: 0, pointerY: 0 } };
      }
      if (normalizedType === 'topology-dots') {
        return { type: normalizedType, value: { pointerX: 0, pointerY: 0 } };
      }
      if (normalizedType === 'radial-burst') {
        return {
          type: normalizedType,
          value: {
            pointerX: 0,
            pointerY: 0,
            lines: Array.from({ length: 240 }, () => ({
              angle: Math.random() * Math.PI * 2,
              speed: 0.00022 + Math.random() * 0.0005,
              lengthOffset: Math.random(),
              colorOffset: Math.random(),
              widthOffset: Math.random(),
              alphaOffset: Math.random(),
            })),
          },
        };
      }
      return { type: normalizedType, value: { pointerX: 0, pointerY: 0 } };
    }
  
    function renderLightningRailsCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const timeSeconds = Math.max(0, now - startTime) * 0.001 * (0.75 + uniformValues.pulseSpeed * 0.55);
      const state = sceneState || { pointerX: 0, pointerY: 0 };
      updateScenePointer(state, mouseState, width, height, 0.05);
      const primaryColor = mixColor(uniformValues.tint, { r: 255, g: 255, b: 255 }, 0.14);
      const accentColor = mixColor(uniformValues.tint, { r: 255, g: 210, b: 255 }, 0.18);
      const spread = 0.14 + uniformValues.lineSpread * 0.22;
      const rails = [width * (0.5 - spread), width * 0.5, width * (0.5 + spread)];
      const centerX = width * 0.5 + state.pointerX * width * 0.04 * uniformValues.mouseInfluence;
      const centerY = height * 0.5 + state.pointerY * height * 0.03 * uniformValues.mouseInfluence;
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, centerX, centerY, Math.max(width, height) * 0.32, uniformValues.tint, 0.05 + uniformValues.intensity * 0.06, 1);
  
      for (let railIndex = 0; railIndex < rails.length; railIndex += 1) {
        const railX = rails[railIndex];
        const railGradient = ctx.createLinearGradient(railX, 0, railX, height);
        railGradient.addColorStop(0, rgbaColor(primaryColor, 0));
        railGradient.addColorStop(0.15, rgbaColor(primaryColor, 0.12 + uniformValues.intensity * 0.12));
        railGradient.addColorStop(0.85, rgbaColor(primaryColor, 0.14 + uniformValues.intensity * 0.14));
        railGradient.addColorStop(1, rgbaColor(primaryColor, 0));
        ctx.strokeStyle = railGradient;
        ctx.lineWidth = 1.1 + uniformValues.intensity * 1.4;
        ctx.beginPath();
        ctx.moveTo(railX, 0);
        ctx.lineTo(railX, height);
        ctx.stroke();
  
        for (let pulseIndex = 0; pulseIndex < 2; pulseIndex += 1) {
          const offset = railIndex * 0.33 + pulseIndex * 0.47;
          const pulseY = (((timeSeconds * (0.18 + uniformValues.pulseSpeed * 0.12) + offset) % 1) * 1.2 - 0.1) * height;
          drawGlow(
            ctx,
            railX + Math.sin(timeSeconds * 2.2 + offset * 7) * width * 0.01,
            pulseY,
            14 + uniformValues.intensity * 20,
            accentColor,
            0.12 + uniformValues.intensity * 0.12,
            1.35
          );
        }
  
        if (Number.isFinite(mouseState?.x) && Number.isFinite(mouseState?.y) && mouseState.x > WEBGL_DEFAULT_MOUSE_X * 0.5) {
          const anchorY = clamp(mouseState.y, 0, height);
          const segments = 11;
          ctx.strokeStyle = rgbaColor(accentColor, 0.08 + uniformValues.intensity * 0.14);
          ctx.lineWidth = 1 + uniformValues.intensity * 0.9;
          ctx.beginPath();
          ctx.moveTo(railX, anchorY);
          for (let segmentIndex = 1; segmentIndex <= segments; segmentIndex += 1) {
            const progress = segmentIndex / segments;
            const px = railX + (mouseState.x - railX) * progress;
            const wave = Math.sin(progress * Math.PI * 4 + timeSeconds * 8 + railIndex) * height * 0.012;
            const py = anchorY + (mouseState.y - anchorY) * progress + wave;
            ctx.lineTo(px, py);
          }
          ctx.stroke();
        }
      }
  
      drawGrain(ctx, width, height, timeSeconds, uniformValues.grain, accentColor);
      ctx.restore();
    }
  
    function renderAtmosphericFoldsCanvas(ctx, width, height, now, startTime, uniformValues) {
      const time = Math.max(0, now - startTime) * 0.001 * 0.09 * uniformValues.pulseSpeed;
      const folds = 28;
      const foldWidth = (width / folds) * (2.4 + uniformValues.lineSpread * 1.8);
      const driftAmplitude = width * (0.03 + uniformValues.lineSpread * 0.03);
      const midColor = mixColor({ r: 14, g: 60, b: 120 }, uniformValues.tint, 0.58);
      const cyanColor = mixColor({ r: 0, g: 160, b: 240 }, uniformValues.tint, 0.68);
      const highlightColor = mixColor({ r: 180, g: 240, b: 255 }, uniformValues.tint, 0.42);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      for (let index = 0; index < folds; index += 1) {
        const normalizedX = index / Math.max(folds - 1, 1);
        const xPos = normalizedX * width + Math.sin(time * 2 + index) * driftAmplitude;
        const baseIntensity = Math.sin(normalizedX * Math.PI) * 0.6 + 0.4;
        const waveIntensity = (Math.sin(time * 3 + index * 0.4) + 1) * 0.5;
        const finalIntensity = baseIntensity * waveIntensity * (0.62 + uniformValues.intensity * 0.9);
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, rgbaColor(midColor, 0));
        gradient.addColorStop(0.4, rgbaColor(midColor, finalIntensity * 0.18));
        gradient.addColorStop(0.72, rgbaColor(cyanColor, finalIntensity * 0.3));
        gradient.addColorStop(1, rgbaColor(highlightColor, finalIntensity * 0.52));
        ctx.fillStyle = gradient;
        ctx.fillRect(xPos - foldWidth * 0.5, 0, foldWidth, height);
      }
      drawGlow(ctx, width * 0.78, height, height * 0.58, cyanColor, 0.08 + uniformValues.intensity * 0.08, 0.85);
      ctx.restore();
    }
  
    function _renderPerspectiveGridCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - startTime) * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, particles: [] };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const horizon = height * (0.36 + state.pointerY * 0.04 * uniformValues.mouseInfluence);
      const centerX = width * 0.5 + state.pointerX * width * 0.08 * uniformValues.mouseInfluence;
      const color = mixColor({ r: 255, g: 255, b: 255 }, uniformValues.tint, 0.65);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.strokeStyle = rgbaColor(color, 0.11 + uniformValues.intensity * 0.12);
      ctx.lineWidth = 1;
  
      const verticalCount = Math.round(10 + uniformValues.lineSpread * 18);
      for (let index = 0; index <= verticalCount; index += 1) {
        const t = index / Math.max(verticalCount, 1);
        const xBottom = t * width;
        const xTop = centerX + (t - 0.5) * width * 0.08;
        ctx.beginPath();
        ctx.moveTo(xBottom, height);
        ctx.lineTo(xTop, horizon);
        ctx.stroke();
      }
  
      const depthCount = Math.round(10 + uniformValues.lineSpread * 16);
      for (let index = 0; index < depthCount; index += 1) {
        const progress = (index + ((time * (0.6 + uniformValues.pulseSpeed * 0.8)) % 1)) / Math.max(depthCount, 1);
        const eased = progress * progress;
        const y = horizon + eased * (height - horizon);
        const inset = width * 0.5 * (1 - Math.pow(progress, 0.72));
        ctx.beginPath();
        ctx.moveTo(centerX - inset, y);
        ctx.lineTo(centerX + inset, y);
        ctx.stroke();
      }
  
      for (let index = 0; index < state.particles.length; index += 1) {
        const particle = state.particles[index];
        const px = width * (0.5 + particle.x * (0.42 + uniformValues.lineSpread * 0.2)) + state.pointerX * width * 0.04;
        const py = horizon + ((particle.y + time * (0.1 + uniformValues.pulseSpeed * 0.05) * particle.size) % 1) * (height - horizon);
        const alpha = 0.08 + uniformValues.intensity * 0.14;
        ctx.fillStyle = rgbaColor(color, alpha);
        ctx.beginPath();
        ctx.arc(px, py, particle.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  
    function renderNetworkDomeCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - startTime) * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, lines: [] };
      updateScenePointer(state, mouseState, width, height, 0.05);
      const cx = width * 0.5 + state.pointerX * width * 0.03 * uniformValues.mouseInfluence;
      const cy = height * (1.02 + state.pointerY * 0.02 * uniformValues.mouseInfluence);
      const radius = Math.max(width, height) * (0.62 + uniformValues.lineSpread * 0.2);
      const lineColor = mixColor({ r: 16, g: 185, b: 129 }, uniformValues.tint, 0.42);
      const particleColor = mixColor({ r: 52, g: 211, b: 153 }, uniformValues.tint, 0.36);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, cx, cy, radius * 0.7, lineColor, 0.08 + uniformValues.intensity * 0.08, 0.75);
  
      for (let index = 0; index < state.lines.length; index += 1) {
        const line = state.lines[index];
        const longitude = line.offset * Math.PI * 2 + time * (0.18 + line.speed * 0.12) * uniformValues.pulseSpeed;
        ctx.beginPath();
        let started = false;
        for (let segmentIndex = 0; segmentIndex <= 42; segmentIndex += 1) {
          const latitude = (segmentIndex / 42) * (Math.PI / 2.15);
          const x = Math.sin(latitude) * Math.cos(longitude);
          const y = Math.cos(latitude);
          const z = Math.sin(latitude) * Math.sin(longitude);
          if (z < -0.62) continue;
          const scale = 0.55 + z * 0.45;
          const screenX = cx + x * radius * scale;
          const screenY = cy - y * radius * scale * 0.72;
          if (!started) {
            ctx.moveTo(screenX, screenY);
            started = true;
          } else {
            ctx.lineTo(screenX, screenY);
          }
        }
        ctx.strokeStyle = rgbaColor(lineColor, 0.05 + uniformValues.intensity * 0.14);
        ctx.lineWidth = 0.6 + (index % 5 === 0 ? 0.6 : 0);
        ctx.stroke();
  
        for (let particleIndex = 0; particleIndex < line.particles.length; particleIndex += 1) {
          const particleT = (line.particles[particleIndex] + time * (0.18 + uniformValues.pulseSpeed * 0.08)) % 1;
          const latitude = particleT * (Math.PI / 2.15);
          const x = Math.sin(latitude) * Math.cos(longitude);
          const y = Math.cos(latitude);
          const z = Math.sin(latitude) * Math.sin(longitude);
          if (z < -0.3) continue;
          const scale = 0.55 + z * 0.45;
          const screenX = cx + x * radius * scale;
          const screenY = cy - y * radius * scale * 0.72;
          ctx.fillStyle = rgbaColor(particleColor, 0.12 + uniformValues.intensity * 0.24);
          ctx.beginPath();
          ctx.arc(screenX, screenY, 0.9 + scale * 1.4, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, particleColor);
      ctx.restore();
    }
  
    function renderAmbientStarfieldCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - startTime) * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, stars: [] };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const starColor = mixColor({ r: 96, g: 255, b: 180 }, uniformValues.tint, 0.72);
      const warmColor = mixColor({ r: 245, g: 180, b: 90 }, uniformValues.tint, 0.32);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, width * 0.5 + state.pointerX * width * 0.05, height * 0.08, Math.max(width, height) * 0.34, starColor, 0.05 + uniformValues.intensity * 0.06, 0.62);
      drawGlow(ctx, width * 0.9, height * 0.9, Math.max(width, height) * 0.26, warmColor, 0.04 + uniformValues.intensity * 0.05, 0.9);
  
      const visibleCount = Math.round(260 + uniformValues.lineSpread * 260);
      for (let index = 0; index < visibleCount; index += 1) {
        const star = state.stars[index];
        const depth = (((star.z - time * (0.08 + uniformValues.pulseSpeed * 0.06) * star.speed) % 1) + 1) % 1;
        const safeDepth = Math.max(depth, 0.035);
        const x = width * 0.5 + ((star.x + state.pointerX * 0.24 * uniformValues.mouseInfluence) / (safeDepth * 2)) * width * 0.18;
        const y = height * 0.5 + ((star.y + state.pointerY * 0.18 * uniformValues.mouseInfluence) / (safeDepth * 2)) * height * 0.18;
        if (x < -8 || x > width + 8 || y < -8 || y > height + 8) continue;
        const twinkle = 0.78 + (Math.sin(time * 2.2 + star.twinkle) + 1) * 0.11;
        const alpha = clamp((1 - safeDepth) * (0.16 + uniformValues.intensity * 0.42) * twinkle, 0.04, 0.86);
        const radius = clamp((1 - safeDepth) * (0.65 + uniformValues.lineSpread) * star.size + 0.15, 0.35, 2.6);
        if (radius > 1.05) {
          ctx.fillStyle = rgbaColor(starColor, alpha * 0.18);
          ctx.beginPath();
          ctx.arc(x, y, radius * 2.2, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = rgbaColor(starColor, alpha);
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, starColor);
      ctx.restore();
    }
  
    function renderTerrainMeshCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - startTime) * 0.001 * 0.9 * uniformValues.pulseSpeed;
      const state = sceneState || { pointerX: 0, pointerY: 0 };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const lineCount = Math.round(24 + uniformValues.lineSpread * 16);
      const points = Math.round(36 + uniformValues.lineSpread * 22);
      const meshColor = mixColor({ r: 168, g: 162, b: 158 }, uniformValues.tint, 0.48);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.translate(0, -height * 0.08 + state.pointerY * height * 0.03 * uniformValues.mouseInfluence);
      ctx.strokeStyle = rgbaColor(meshColor, 0.1 + uniformValues.intensity * 0.16);
      ctx.lineWidth = 0.7 + uniformValues.intensity * 0.4;
  
      for (let lineIndex = 0; lineIndex <= lineCount; lineIndex += 1) {
        ctx.beginPath();
        for (let pointIndex = 0; pointIndex <= points; pointIndex += 1) {
          const x = (pointIndex / points) * width;
          const yBase = height * 0.18 + (lineIndex / Math.max(lineCount, 1)) * height * 0.92;
          const wave1 = Math.sin(x * 0.003 + time + lineIndex * 0.11 + state.pointerX * 0.8) * (22 + uniformValues.intensity * 22);
          const wave2 = Math.sin(x * 0.007 - time * 0.8) * (10 + uniformValues.intensity * 12);
          const wave3 = Math.cos(lineIndex * 0.18 + time * 1.1 + state.pointerY * 0.7) * (10 + uniformValues.intensity * 8);
          const perspectiveShift = ((lineIndex / Math.max(lineCount, 1)) - 0.5) * state.pointerX * width * 0.07 * uniformValues.mouseInfluence;
          const y = yBase + wave1 + wave2 + wave3;
          if (pointIndex === 0) ctx.moveTo(x + perspectiveShift, y);
          else ctx.lineTo(x + perspectiveShift, y);
        }
        ctx.stroke();
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, meshColor);
      ctx.restore();
    }
  
    function _renderRevenueBarsCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - startTime) * 0.001 * (1.15 + uniformValues.pulseSpeed * 0.35);
      const state = sceneState || { pointerX: 0, pointerY: 0, detail: [] };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const count = Math.round(44 + uniformValues.lineSpread * 60);
      const barWidth = width / Math.max(count, 1);
      const barColor = mixColor({ r: 17, g: 17, b: 17 }, uniformValues.tint, 0.54);
      const reflectionColor = mixColor({ r: 204, g: 204, b: 204 }, uniformValues.tint, 0.32);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
  
      for (let index = 0; index < count; index += 1) {
        const x = index * barWidth;
        const center = (index / Math.max(count - 1, 1)) * 2 - 1;
        const envelope = Math.max(0, 1 - Math.abs(center) * 1.25);
        const noise1 = Math.sin(index * 0.22 + time * 1.8) * Math.cos(index * 0.11 + time * 0.8);
        const noise2 = Math.sin(index * 0.45 - time * 1.35) * 0.5;
        const noise3 = state.detail[index % state.detail.length];
        const scaleY = Math.max(0.08, Math.abs(noise1 + noise2 + noise3) * (0.22 + uniformValues.intensity * 0.42) * envelope);
        const barHeight = scaleY * height * 0.6;
        const skew = state.pointerX * uniformValues.mouseInfluence * width * 0.03;
        const yShift = -state.pointerY * uniformValues.mouseInfluence * height * 0.03;
        ctx.fillStyle = rgbaColor(barColor, 0.7 + uniformValues.intensity * 0.2);
        ctx.fillRect(x + skew, height * 0.5 - barHeight + yShift, Math.max(1, barWidth * 0.62), barHeight);
        ctx.fillStyle = rgbaColor(reflectionColor, 0.09 + uniformValues.intensity * 0.12);
        ctx.fillRect(x + skew, height * 0.5 + 4 + yShift, Math.max(1, barWidth * 0.62), barHeight * 0.58);
      }
  
      drawGrain(ctx, width, height, time, uniformValues.grain, reflectionColor);
      ctx.restore();
    }
  
    function renderTopologyDotsCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - startTime) * 0.001 * (0.95 + uniformValues.pulseSpeed * 0.45);
      const state = sceneState || { pointerX: 0, pointerY: 0 };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const step = Math.max(10, Math.round(22 - uniformValues.lineSpread * 10));
      const dotColor = mixColor({ r: 96, g: 165, b: 250 }, uniformValues.tint, 0.72);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      for (let x = 0; x <= width; x += step) {
        for (let y = 0; y <= height; y += step) {
          const waveX = Math.sin(x * 0.01 + time + state.pointerX * 0.9) * (18 + uniformValues.intensity * 26);
          const waveY = Math.cos(y * 0.01 + time * 0.7 + state.pointerY * 0.8) * (16 + uniformValues.intensity * 22);
          const targetY = height * 0.5 + waveX + waveY;
          const distance = Math.abs(y - targetY);
          const radius = Math.max(0.4, 2.6 - distance * (0.011 + uniformValues.lineSpread * 0.004));
          const alpha = Math.max(0.04, 0.8 - distance * (0.0038 - uniformValues.lineSpread * 0.0005));
          if (alpha <= 0.04 && radius <= 0.5) continue;
          const screenX = x + state.pointerX * 7 * uniformValues.mouseInfluence;
          const screenY = y + state.pointerY * 6 * uniformValues.mouseInfluence;
          ctx.fillStyle = rgbaColor(dotColor, alpha);
          ctx.beginPath();
          ctx.arc(screenX, screenY, radius, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, dotColor);
      ctx.restore();
    }
  
    function renderRadialBurstCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const elapsedMilliseconds = Math.max(0, now - startTime);
      const elapsedSeconds = elapsedMilliseconds * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, lines: [] };
      updateScenePointer(state, mouseState, width, height, 0.05);
      const lineCount = Math.round(170 + uniformValues.lineSpread * 150);
      while (state.lines.length < lineCount) {
        state.lines.push({
          angle: Math.random() * Math.PI * 2,
          speed: 0.00022 + Math.random() * 0.0005,
          lengthOffset: Math.random(),
          colorOffset: Math.random(),
          widthOffset: Math.random(),
          alphaOffset: Math.random(),
        });
      }
  
      const centerX = width * 0.5 + state.pointerX * width * 0.06 * uniformValues.mouseInfluence;
      const centerY = height * 0.5 + state.pointerY * height * 0.045 * uniformValues.mouseInfluence;
      const maxRadius = Math.max(width, height) * (0.55 + uniformValues.intensity * 0.32);
      const innerRadius = Math.max(18, Math.min(width, height) * (0.09 + (1 - uniformValues.lineSpread) * 0.05));
      const primaryColor = mixColor({ r: 59, g: 130, b: 246 }, uniformValues.tint, 0.45);
      const accentColor = mixColor({ r: 139, g: 92, b: 246 }, uniformValues.tint, 0.35);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, centerX, centerY, maxRadius * 0.42, uniformValues.tint, 0.08 + uniformValues.intensity * 0.08, 1);
  
      for (let index = 0; index < lineCount; index += 1) {
        const line = state.lines[index];
        line.angle += line.speed * (0.75 + uniformValues.pulseSpeed * 0.55);
        const currentAngle = line.angle + state.pointerX * 0.08 * uniformValues.mouseInfluence;
        const pulse = Math.sin(elapsedMilliseconds * 0.0021 + line.lengthOffset * Math.PI * 2) * 0.2 + 0.82;
        const length = maxRadius * (0.62 + pulse * (0.24 + uniformValues.intensity * 0.22));
        const startX = centerX + Math.cos(currentAngle) * innerRadius;
        const startY = centerY + Math.sin(currentAngle) * innerRadius;
        const endX = centerX + Math.cos(currentAngle) * length;
        const endY = centerY + Math.sin(currentAngle) * length;
        const lineColor = line.colorOffset > 0.5 ? primaryColor : accentColor;
        const opacityBase = 0.08 + uniformValues.intensity * 0.22 + line.alphaOffset * 0.12;
        const opacity = opacityBase * (0.75 + Math.sin(elapsedMilliseconds * 0.0012 + line.alphaOffset * Math.PI * 2) * 0.25);
        const gradient = ctx.createLinearGradient(startX, startY, endX, endY);
        gradient.addColorStop(0, rgbaColor(lineColor, 0));
        gradient.addColorStop(0.18, rgbaColor(lineColor, opacity));
        gradient.addColorStop(0.82, rgbaColor(lineColor, opacity * 0.52));
        gradient.addColorStop(1, rgbaColor(lineColor, 0));
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 1 + line.widthOffset * (1.2 + uniformValues.intensity * 1.1);
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.stroke();
      }
      drawGrain(ctx, width, height, elapsedSeconds, uniformValues.grain, accentColor);
      ctx.restore();
    }
  
    function renderCanvasOverlayFrame(ctx, width, height, now, startTime, uniformValues, mouseState, sceneState) {
      const overlayType = getWebglOverlayType(uniformValues?.overlayType);
      const state = sceneState || createCanvasOverlaySceneState(overlayType).value;
      switch (overlayType) {
        case 'atmospheric-folds':
          renderAtmosphericFoldsCanvas(ctx, width, height, now, startTime, uniformValues);
          return;
        case 'network-dome':
          renderNetworkDomeCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, state);
          return;
        case 'ambient-starfield':
          renderAmbientStarfieldCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, state);
          return;
        case 'terrain-mesh':
          renderTerrainMeshCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, state);
          return;
        case 'topology-dots':
          renderTopologyDotsCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, state);
          return;
        case 'radial-burst':
          renderRadialBurstCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, state);
          return;
        case 'lightning-rails':
        default:
          renderLightningRailsCanvas(ctx, width, height, now, startTime, uniformValues, mouseState, state);
      }
    }
  
    globalScope.__ASCII_WEBGL_OVERLAY_SHARED__ = {
      WEBGL_OVERLAY_TYPES,
      getWebglOverlayType,
      isCanvasOverlayType,
      getWebglOverlayFragmentSource,
      getWebglOverlayUniformValues,
      ensureWebglOverlayResources,
      disposeWebglOverlayResources,
      renderShaderOverlayFrame,
      createCanvasOverlaySceneState,
      renderCanvasOverlayFrame,
    };
  })(typeof globalThis !== 'undefined' ? globalThis : window);
  
    const webglOverlayShared = (typeof globalThis !== 'undefined' ? globalThis : window).__ASCII_WEBGL_OVERLAY_SHARED__;
    const WEBGL_OVERLAY_VERTEX_SHADER = "\nattribute vec2 aVertexPosition;\nvoid main() {\n  gl_Position = vec4(aVertexPosition, 0.0, 1.0);\n}\n";
    const WEBGL_OVERLAY_FRAGMENT_SHADER = "\n#ifdef GL_FRAGMENT_PRECISION_HIGH\nprecision highp float;\n#else\nprecision mediump float;\n#endif\nuniform vec2 u_resolution;\nuniform float u_time;\nuniform vec2 u_mouse;\nuniform float u_mouseActive;\nuniform float u_lineSpread;\nuniform float u_intensity;\nuniform float u_lightning;\nuniform float u_pulse;\nuniform float u_mouseInfluence;\nuniform float u_grain;\nuniform vec3 u_tint;\n\nfloat hash(float n) {\n  return fract(sin(n) * 753.5453123);\n}\n\nfloat noise(float x) {\n  float i = floor(x);\n  float f = fract(x);\n  f = f * f * (3.0 - 2.0 * f);\n  return mix(hash(i), hash(i + 1.0), f);\n}\n\nfloat lightning(vec2 uv, vec2 a, vec2 b, float t) {\n  vec2 ab = b - a;\n  float len = length(ab);\n  if (len < 0.01) return 0.0;\n\n  vec2 dir = ab / len;\n  vec2 pa = uv - a;\n  float h = clamp(dot(pa, dir) / len, 0.0, 1.0);\n  float dist = length(pa - dir * (h * len));\n  float env = sin(h * 3.14159265);\n\n  float offset = (noise(h * 15.0 - t * 20.0) - 0.5) * 0.1 * env;\n  offset += (noise(h * 40.0 + t * 30.0) - 0.5) * 0.03 * env;\n  float d = abs(dist + offset);\n\n  return (0.0003 / (d + 0.0003) + 0.00002 / (d * d + 0.00002)) * env;\n}\n\nfloat pulseBand(float distanceToRail, float y, float t, float speed, float offset, float strength) {\n  float pulseY = fract(t * speed + offset) * 4.0 - 2.0;\n  return smoothstep(0.4, 0.0, abs(y - pulseY)) * strength / (distanceToRail + 0.002);\n}\n\nfloat wave(float y, float t, float offset, float amplitude) {\n  return sin(y * 10.0 + t * 2.0 + offset) * amplitude;\n}\n\nvoid main() {\n  vec2 safeResolution = max(u_resolution.xy, vec2(1.0));\n  vec2 uv = gl_FragCoord.xy / safeResolution;\n  uv = uv * 2.0 - 1.0;\n  uv.x *= safeResolution.x / safeResolution.y;\n\n  vec2 mouseUV = u_mouse / safeResolution;\n  mouseUV = mouseUV * 2.0 - 1.0;\n  mouseUV.x *= safeResolution.x / safeResolution.y;\n\n  float spreadMix = clamp((u_lineSpread - 0.1) / 0.45, 0.0, 1.0);\n  float spread = mix(0.12, 0.2, spreadMix);\n  float pulseSpeed = max(0.1, u_pulse);\n  float intensity = clamp(u_intensity, 0.0, 1.0);\n  float lightningAmount = clamp(u_lightning, 0.0, 1.8);\n  float mouseInfluence = clamp(u_mouseInfluence, 0.0, 2.0);\n  float grainAmount = clamp(u_grain, 0.0, 0.12);\n  float t = u_time * 0.5;\n  float outerOffset = spread + mix(0.016, 0.028, spreadMix);\n  float waveAmplitude = (0.004 + lightningAmount * 0.0015) * (0.85 + spreadMix * 0.25);\n\n  float d1 = abs(uv.x - (-spread));\n  float d2 = abs(uv.x - 0.0);\n  float d3 = abs(uv.x - spread);\n\n  float baseIntensity = mix(0.003, 0.0065, intensity);\n  float glow = baseIntensity / (d1 + 0.002);\n  glow += baseIntensity / (d2 + 0.002);\n  glow += baseIntensity / (d3 + 0.002);\n\n  glow += pulseBand(d1, uv.y, t, 0.2 * pulseSpeed, 0.0, 0.018 + intensity * 0.016) * 1.2;\n  glow += pulseBand(d2, uv.y, t, 0.25 * pulseSpeed, 0.3, 0.018 + intensity * 0.016) * 1.2;\n  glow += pulseBand(d3, uv.y, t, 0.15 * pulseSpeed, 0.7, 0.018 + intensity * 0.016) * 1.2;\n\n  float wD1a = abs(uv.x - (-outerOffset + wave(uv.y, t, 0.0, waveAmplitude)));\n  float wD1b = abs(uv.x - (-(spread - 0.02) + wave(uv.y, t, 1.0, waveAmplitude)));\n  float wD2a = abs(uv.x - (-0.02 + wave(uv.y, t, 2.0, waveAmplitude)));\n  float wD2b = abs(uv.x - ( 0.02 + wave(uv.y, t, 3.0, waveAmplitude)));\n  float wD3a = abs(uv.x - ((spread - 0.02) + wave(uv.y, t, 4.0, waveAmplitude)));\n  float wD3b = abs(uv.x - (outerOffset + wave(uv.y, t, 5.0, waveAmplitude)));\n\n  float wavePulseStrength = (0.003 + intensity * 0.005) * (0.35 + lightningAmount * 0.2);\n  glow += pulseBand(wD1a, uv.y, t, 0.3 * pulseSpeed, 0.1, wavePulseStrength);\n  glow += pulseBand(wD1b, uv.y, t, 0.22 * pulseSpeed, 0.6, wavePulseStrength);\n  glow += pulseBand(wD2a, uv.y, t, 0.28 * pulseSpeed, 0.2, wavePulseStrength);\n  glow += pulseBand(wD2b, uv.y, t, 0.32 * pulseSpeed, 0.8, wavePulseStrength);\n  glow += pulseBand(wD3a, uv.y, t, 0.35 * pulseSpeed, 0.4, wavePulseStrength);\n  glow += pulseBand(wD3b, uv.y, t, 0.25 * pulseSpeed, 0.9, wavePulseStrength);\n\n  vec2 p1 = vec2(-spread, mouseUV.y);\n  vec2 p2 = vec2(0.0, mouseUV.y);\n  vec2 p3 = vec2(spread, mouseUV.y);\n\n  float flickerGate = step(0.15, noise(t * (40.0 + pulseSpeed * 12.0)));\n  float flicker = flickerGate * (noise(t * (100.0 + pulseSpeed * 20.0)) * 0.7 + 0.3);\n  float mouseActivation = clamp(u_mouseActive, 0.0, 1.0) * mouseInfluence;\n  float mouseRadius = mix(1.4, 2.7, clamp(mouseInfluence * 0.5, 0.0, 1.0));\n\n  glow += lightning(uv, p1, mouseUV, t) * smoothstep(mouseRadius, 0.0, length(mouseUV - p1)) * mouseActivation * flicker * lightningAmount;\n  glow += lightning(uv, p2, mouseUV, t + 10.0) * smoothstep(mouseRadius, 0.0, length(mouseUV - p2)) * mouseActivation * flicker * lightningAmount;\n  glow += lightning(uv, p3, mouseUV, t + 20.0) * smoothstep(mouseRadius, 0.0, length(mouseUV - p3)) * mouseActivation * flicker * lightningAmount;\n\n  float distToCenter = length(uv);\n  glow += (0.014 + intensity * 0.03) / (distToCenter + 0.02);\n\n  vec3 tintColor = max(u_tint, vec3(0.06));\n  vec3 railColor = mix(tintColor * 0.55, tintColor * 1.15, 0.72);\n  vec3 highlightColor = mix(tintColor, vec3(1.0), 0.2 + intensity * 0.18);\n  float shimmer = 0.8 + 0.2 * sin(t * (1.5 + pulseSpeed * 0.15) - distToCenter * 5.0);\n  float falloff = 1.0 - smoothstep(0.3, 2.2, distToCenter);\n\n  vec3 finalColor = railColor * glow * shimmer;\n  finalColor += highlightColor * pow(max(glow, 0.0), 1.28) * (0.05 + lightningAmount * 0.02);\n  finalColor *= falloff;\n  float n = fract(sin(dot(gl_FragCoord.xy, vec2(12.9898, 78.233))) * 43758.5453);\n  finalColor += (n - 0.5) * grainAmount * 0.32;\n  finalColor = max(finalColor, vec3(0.0));\n\n  float luminance = dot(finalColor, vec3(0.2126, 0.7152, 0.0722));\n  float alpha = clamp(luminance * (1.2 + intensity * 1.4), 0.0, 0.98);\n  gl_FragColor = vec4(finalColor, alpha);\n}\n";
  
    function parseHexColor(value, fallback) {
      const fallbackColor = fallback || { r: 153, g: 187, b: 255 };
      if (typeof value !== 'string') return fallbackColor;
      const trimmed = value.trim();
      const match = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(trimmed);
      if (!match) return fallbackColor;
      const hex = match[1].length === 3
        ? match[1].split('').map((char) => char + char).join('')
        : match[1];
      return {
        r: parseInt(hex.slice(0, 2), 16),
        g: parseInt(hex.slice(2, 4), 16),
        b: parseInt(hex.slice(4, 6), 16)
      };
    }
  
    function createShader(gl, type, source) {
      const shader = gl.createShader(type);
      if (!shader) return null;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        gl.deleteShader(shader);
        return null;
      }
      return shader;
    }
  
    function createWebglProgram(gl, vertexSource, fragmentSource) {
      const vertexShader = createShader(gl, gl.VERTEX_SHADER, vertexSource);
      const fragmentShader = createShader(gl, gl.FRAGMENT_SHADER, fragmentSource);
      if (!vertexShader || !fragmentShader) {
        if (vertexShader) gl.deleteShader(vertexShader);
        if (fragmentShader) gl.deleteShader(fragmentShader);
        return null;
      }
      const program = gl.createProgram();
      if (!program) {
        gl.deleteShader(vertexShader);
        gl.deleteShader(fragmentShader);
        return null;
      }
      gl.attachShader(program, vertexShader);
      gl.attachShader(program, fragmentShader);
      gl.linkProgram(program);
      gl.deleteShader(vertexShader);
      gl.deleteShader(fragmentShader);
      if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
        gl.deleteProgram(program);
        return null;
      }
      return program;
    }
  
    function ensureWebglShaderResources(gl) {
      if (!gl) return null;
      if (webglShaderResources) return webglShaderResources;
      webglShaderResources = webglOverlayShared.ensureWebglOverlayResources(gl);
      return webglShaderResources;
    }
  
    function disposeWebglShaderResources() {
      if (!webglShaderGl || !webglShaderResources) return;
      webglOverlayShared.disposeWebglOverlayResources(webglShaderGl, webglShaderResources);
      webglShaderResources = null;
    }
  
    function updateWebglMouseActivity(now, width, height) {
      if (pointer.inside) {
        webglMouseState.x = clamp((pointer.x / Math.max(renderWidth, 1)) * width, 0, width);
        webglMouseState.y = clamp((pointer.y / Math.max(renderHeight, 1)) * height, 0, height);
        webglMouseState.lastMove = now;
      } else {
        webglMouseState.x = WEBGL_DEFAULT_MOUSE_X;
        webglMouseState.y = WEBGL_DEFAULT_MOUSE_Y;
      }
      const timeSinceMove = now - webglMouseState.lastMove;
      const targetMouseActive =
        timeSinceMove < WEBGL_MOUSE_IDLE_MS
          ? 1
          : Math.max(0, 1 - (timeSinceMove - WEBGL_MOUSE_IDLE_MS) / WEBGL_MOUSE_FADE_MS);
      webglMouseState.active += (targetMouseActive - webglMouseState.active) * 0.15;
    }
  
    function rgbaColor(color, alpha) {
      return 'rgba(' + color.r + ', ' + color.g + ', ' + color.b + ', ' + clamp(alpha, 0, 1) + ')';
    }
  
    function mixColor(colorA, colorB, amount) {
      return {
        r: lerpChannel(colorA.r, colorB.r, amount),
        g: lerpChannel(colorA.g, colorB.g, amount),
        b: lerpChannel(colorA.b, colorB.b, amount)
      };
    }
  
    function scaleColor(color, factor) {
      return {
        r: clamp(Math.round(color.r * factor), 0, 255),
        g: clamp(Math.round(color.g * factor), 0, 255),
        b: clamp(Math.round(color.b * factor), 0, 255)
      };
    }
  
    function getWebglOverlayType(value) {
      return webglOverlayShared.getWebglOverlayType(value);
    }
  
    function getWebglUniformValues() {
      return webglOverlayShared.getWebglOverlayUniformValues(SETTINGS);
    }
  
    function isWebglLayerActive() {
      return Boolean(SETTINGS.webglLayerEnabled);
    }
  
    function isWebglAsciiFxEnabled() {
      return isWebglLayerActive() && Boolean(SETTINGS.webglOverlayAffectsAscii);
    }
  
    function isSeparateWebglVisible(uniformValues) {
      return isWebglLayerActive() && !Boolean(SETTINGS.webglOverlayAffectsAscii) && (uniformValues?.opacity ?? 0) > 0.001;
    }
  
    function usesShaderOverlay(uniformValues) {
      return Boolean(webglShaderGl) && !webglOverlayShared.isCanvasOverlayType(uniformValues?.overlayType);
    }
  
    function syncWebglLayerStyle(uniformValues) {
      const visible = isSeparateWebglVisible(uniformValues);
      const useShader = visible && usesShaderOverlay(uniformValues);
      const targetZIndex = SETTINGS.webglOverlayPosition === 'above' ? '3' : '1';
      webglCanvas.style.display = visible && !useShader ? 'block' : 'none';
      webglCanvas.style.opacity = visible && !useShader ? String(uniformValues.opacity) : '0';
      webglCanvas.style.zIndex = targetZIndex;
      webglShaderCanvas.style.display = useShader ? 'block' : 'none';
      webglShaderCanvas.style.opacity = useShader ? String(uniformValues.opacity) : '0';
      webglShaderCanvas.style.zIndex = targetZIndex;
    }
  
    function syncOverlayCanvasSize(targetCanvas, targetCtx, width, height, pixelRatio) {
      const ratio = Math.max(1, Number(pixelRatio) || 1);
      const nextWidth = Math.max(1, Math.round(width * ratio));
      const nextHeight = Math.max(1, Math.round(height * ratio));
      if (targetCanvas.width !== nextWidth || targetCanvas.height !== nextHeight) {
        targetCanvas.width = nextWidth;
        targetCanvas.height = nextHeight;
      }
      targetCtx.setTransform(ratio, 0, 0, ratio, 0, 0);
    }
  
    function syncShaderCanvasSize(width, height, pixelRatio) {
      const ratio = Math.max(1, Number(pixelRatio) || 1);
      const nextWidth = Math.max(1, Math.round(width * ratio));
      const nextHeight = Math.max(1, Math.round(height * ratio));
      if (webglShaderCanvas.width !== nextWidth || webglShaderCanvas.height !== nextHeight) {
        webglShaderCanvas.width = nextWidth;
        webglShaderCanvas.height = nextHeight;
      }
    }
  
    function getWebglMouseState(width, height) {
      if (!pointer.inside || renderWidth <= 0 || renderHeight <= 0) {
        return { x: WEBGL_DEFAULT_MOUSE_X, y: WEBGL_DEFAULT_MOUSE_Y };
      }
      return {
        x: clamp((pointer.x / Math.max(renderWidth, 1)) * width, 0, width),
        y: clamp((pointer.y / Math.max(renderHeight, 1)) * height, 0, height)
      };
    }
  
    function renderShaderOverlayFrame(width, height, now, uniformValues) {
      const gl = webglShaderGl;
      if (!gl || width <= 0 || height <= 0) return;
      const resources = ensureWebglShaderResources(gl);
      if (!resources) return;
      updateWebglMouseActivity(now, width, height);
      webglOverlayShared.renderShaderOverlayFrame(
        gl,
        resources,
        webglShaderCanvas.width,
        webglShaderCanvas.height,
        now,
        webglStartTime,
        webglMouseState,
        uniformValues
      );
    }
  
    function ensureWebglSceneState(overlayType) {
      const normalizedType = getWebglOverlayType(overlayType);
      if (webglScene && webglScene.type === normalizedType) return webglScene.value;
      webglScene = webglOverlayShared.createCanvasOverlaySceneState(normalizedType);
      return webglScene?.value || null;
    }
  
    function updateScenePointer(state, mouseState, width, height, smoothing) {
      if (!state) return;
      const hasMouse =
        Number.isFinite(mouseState?.x) &&
        Number.isFinite(mouseState?.y) &&
        mouseState.x > WEBGL_DEFAULT_MOUSE_X * 0.5 &&
        mouseState.y > WEBGL_DEFAULT_MOUSE_Y * 0.5;
      const mouseNormX = hasMouse ? (mouseState.x / Math.max(width, 1) - 0.5) * 2 : 0;
      const mouseNormY = hasMouse ? (mouseState.y / Math.max(height, 1) - 0.5) * 2 : 0;
      const amount = clamp(Number(smoothing) || 0.04, 0.01, 0.2);
      state.pointerX += (mouseNormX - state.pointerX) * amount;
      state.pointerY += (mouseNormY - state.pointerY) * amount;
    }
  
    function drawGlow(ctx, x, y, radius, color, alpha, verticalScale) {
      const scaleY = Math.max(0.2, Number(verticalScale) || 1);
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(1, scaleY);
      const gradient = ctx.createRadialGradient(0, 0, 0, 0, 0, radius);
      gradient.addColorStop(0, rgbaColor(color, alpha));
      gradient.addColorStop(0.45, rgbaColor(scaleColor(color, 0.78), alpha * 0.42));
      gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(0, 0, radius, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    }
  
    function drawGrain(ctx, width, height, nowSeconds, amount, color) {
      if (amount <= 0.002) return;
      const count = Math.round(24 + amount * 220);
      ctx.save();
      ctx.globalCompositeOperation = 'overlay';
      ctx.fillStyle = rgbaColor(color, 0.018 + amount * 0.08);
      for (let index = 0; index < count; index += 1) {
        const seed = index * 12.713 + nowSeconds * 2.3;
        const gx = ((Math.sin(seed) * 43758.5453) % 1 + 1) % 1;
        const gy = ((Math.sin(seed * 1.67) * 24634.6345) % 1 + 1) % 1;
        ctx.fillRect(Math.floor(gx * width), Math.floor(gy * height), 1, 1);
      }
      ctx.restore();
    }
  
    function renderLightningRailsWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const timeSeconds = Math.max(0, now - webglStartTime) * 0.001 * (0.75 + uniformValues.pulseSpeed * 0.55);
      const state = sceneState || { pointerX: 0, pointerY: 0 };
      updateScenePointer(state, mouseState, width, height, 0.05);
      const primaryColor = mixColor(uniformValues.tint, { r: 255, g: 255, b: 255 }, 0.14);
      const accentColor = mixColor(uniformValues.tint, { r: 255, g: 210, b: 255 }, 0.18);
      const spread = 0.14 + uniformValues.lineSpread * 0.22;
      const rails = [
        width * (0.5 - spread),
        width * 0.5,
        width * (0.5 + spread)
      ];
      const centerX = width * 0.5 + state.pointerX * width * 0.04 * uniformValues.mouseInfluence;
      const centerY = height * 0.5 + state.pointerY * height * 0.03 * uniformValues.mouseInfluence;
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, centerX, centerY, Math.max(width, height) * 0.32, uniformValues.tint, 0.05 + uniformValues.intensity * 0.06, 1);
  
      for (let railIndex = 0; railIndex < rails.length; railIndex += 1) {
        const railX = rails[railIndex];
        const railGradient = ctx.createLinearGradient(railX, 0, railX, height);
        railGradient.addColorStop(0, rgbaColor(primaryColor, 0));
        railGradient.addColorStop(0.15, rgbaColor(primaryColor, 0.12 + uniformValues.intensity * 0.12));
        railGradient.addColorStop(0.85, rgbaColor(primaryColor, 0.14 + uniformValues.intensity * 0.14));
        railGradient.addColorStop(1, rgbaColor(primaryColor, 0));
        ctx.strokeStyle = railGradient;
        ctx.lineWidth = 1.1 + uniformValues.intensity * 1.4;
        ctx.beginPath();
        ctx.moveTo(railX, 0);
        ctx.lineTo(railX, height);
        ctx.stroke();
  
        for (let pulseIndex = 0; pulseIndex < 2; pulseIndex += 1) {
          const offset = railIndex * 0.33 + pulseIndex * 0.47;
          const pulseY = (((timeSeconds * (0.18 + uniformValues.pulseSpeed * 0.12) + offset) % 1) * 1.2 - 0.1) * height;
          drawGlow(
            ctx,
            railX + Math.sin(timeSeconds * 2.2 + offset * 7) * width * 0.01,
            pulseY,
            14 + uniformValues.intensity * 20,
            accentColor,
            0.12 + uniformValues.intensity * 0.12,
            1.35
          );
        }
  
        if (Number.isFinite(mouseState?.x) && Number.isFinite(mouseState?.y) && mouseState.x > WEBGL_DEFAULT_MOUSE_X * 0.5) {
          const anchorY = clamp(mouseState.y, 0, height);
          const segments = 11;
          ctx.strokeStyle = rgbaColor(accentColor, 0.08 + uniformValues.intensity * 0.14);
          ctx.lineWidth = 1 + uniformValues.intensity * 0.9;
          ctx.beginPath();
          ctx.moveTo(railX, anchorY);
          for (let segmentIndex = 1; segmentIndex <= segments; segmentIndex += 1) {
            const progress = segmentIndex / segments;
            const px = railX + (mouseState.x - railX) * progress;
            const wave = Math.sin(progress * Math.PI * 4 + timeSeconds * 8 + railIndex) * height * 0.012;
            const py = anchorY + (mouseState.y - anchorY) * progress + wave;
            ctx.lineTo(px, py);
          }
          ctx.stroke();
        }
      }
  
      drawGrain(ctx, width, height, timeSeconds, uniformValues.grain, accentColor);
      ctx.restore();
    }
  
    function renderAtmosphericFoldsWebgl(ctx, width, height, now, uniformValues) {
      const time = Math.max(0, now - webglStartTime) * 0.001 * 0.09 * uniformValues.pulseSpeed;
      const folds = 28;
      const foldWidth = (width / folds) * (2.4 + uniformValues.lineSpread * 1.8);
      const driftAmplitude = width * (0.03 + uniformValues.lineSpread * 0.03);
      const midColor = mixColor({ r: 14, g: 60, b: 120 }, uniformValues.tint, 0.58);
      const cyanColor = mixColor({ r: 0, g: 160, b: 240 }, uniformValues.tint, 0.68);
      const highlightColor = mixColor({ r: 180, g: 240, b: 255 }, uniformValues.tint, 0.42);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      for (let index = 0; index < folds; index += 1) {
        const normalizedX = index / Math.max(folds - 1, 1);
        const xPos = normalizedX * width + Math.sin(time * 2 + index) * driftAmplitude;
        const baseIntensity = Math.sin(normalizedX * Math.PI) * 0.6 + 0.4;
        const waveIntensity = (Math.sin(time * 3 + index * 0.4) + 1) * 0.5;
        const finalIntensity = baseIntensity * waveIntensity * (0.62 + uniformValues.intensity * 0.9);
        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        gradient.addColorStop(0, rgbaColor(midColor, 0));
        gradient.addColorStop(0.4, rgbaColor(midColor, finalIntensity * 0.18));
        gradient.addColorStop(0.72, rgbaColor(cyanColor, finalIntensity * 0.3));
        gradient.addColorStop(1, rgbaColor(highlightColor, finalIntensity * 0.52));
        ctx.fillStyle = gradient;
        ctx.fillRect(xPos - foldWidth * 0.5, 0, foldWidth, height);
      }
      drawGlow(ctx, width * 0.78, height, height * 0.58, cyanColor, 0.08 + uniformValues.intensity * 0.08, 0.85);
      ctx.restore();
    }
  
    function renderPerspectiveGridWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - webglStartTime) * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, particles: [] };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const horizon = height * (0.36 + state.pointerY * 0.04 * uniformValues.mouseInfluence);
      const centerX = width * 0.5 + state.pointerX * width * 0.08 * uniformValues.mouseInfluence;
      const color = mixColor({ r: 255, g: 255, b: 255 }, uniformValues.tint, 0.65);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.strokeStyle = rgbaColor(color, 0.11 + uniformValues.intensity * 0.12);
      ctx.lineWidth = 1;
  
      const verticalCount = Math.round(10 + uniformValues.lineSpread * 18);
      for (let index = 0; index <= verticalCount; index += 1) {
        const t = index / Math.max(verticalCount, 1);
        const xBottom = t * width;
        const xTop = centerX + (t - 0.5) * width * 0.08;
        ctx.beginPath();
        ctx.moveTo(xBottom, height);
        ctx.lineTo(xTop, horizon);
        ctx.stroke();
      }
  
      const depthCount = Math.round(10 + uniformValues.lineSpread * 16);
      for (let index = 0; index < depthCount; index += 1) {
        const progress = (index + ((time * (0.6 + uniformValues.pulseSpeed * 0.8)) % 1)) / Math.max(depthCount, 1);
        const eased = progress * progress;
        const y = horizon + eased * (height - horizon);
        const inset = width * 0.5 * (1 - Math.pow(progress, 0.72));
        ctx.beginPath();
        ctx.moveTo(centerX - inset, y);
        ctx.lineTo(centerX + inset, y);
        ctx.stroke();
      }
  
      for (let index = 0; index < state.particles.length; index += 1) {
        const particle = state.particles[index];
        const px = width * (0.5 + particle.x * (0.42 + uniformValues.lineSpread * 0.2)) + state.pointerX * width * 0.04;
        const py = horizon + ((particle.y + time * (0.1 + uniformValues.pulseSpeed * 0.05) * particle.size) % 1) * (height - horizon);
        const alpha = 0.08 + uniformValues.intensity * 0.14;
        ctx.fillStyle = rgbaColor(color, alpha);
        ctx.beginPath();
        ctx.arc(px, py, particle.size, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.restore();
    }
  
    function renderNetworkDomeWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - webglStartTime) * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, lines: [] };
      updateScenePointer(state, mouseState, width, height, 0.05);
      const cx = width * 0.5 + state.pointerX * width * 0.03 * uniformValues.mouseInfluence;
      const cy = height * (1.02 + state.pointerY * 0.02 * uniformValues.mouseInfluence);
      const radius = Math.max(width, height) * (0.62 + uniformValues.lineSpread * 0.2);
      const lineColor = mixColor({ r: 16, g: 185, b: 129 }, uniformValues.tint, 0.42);
      const particleColor = mixColor({ r: 52, g: 211, b: 153 }, uniformValues.tint, 0.36);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, cx, cy, radius * 0.7, lineColor, 0.08 + uniformValues.intensity * 0.08, 0.75);
  
      for (let index = 0; index < state.lines.length; index += 1) {
        const line = state.lines[index];
        const longitude = line.offset * Math.PI * 2 + time * (0.18 + line.speed * 0.12) * uniformValues.pulseSpeed;
        ctx.beginPath();
        let started = false;
        for (let segmentIndex = 0; segmentIndex <= 42; segmentIndex += 1) {
          const latitude = (segmentIndex / 42) * (Math.PI / 2.15);
          const x = Math.sin(latitude) * Math.cos(longitude);
          const y = Math.cos(latitude);
          const z = Math.sin(latitude) * Math.sin(longitude);
          if (z < -0.62) continue;
          const scale = 0.55 + z * 0.45;
          const screenX = cx + x * radius * scale;
          const screenY = cy - y * radius * scale * 0.72;
          if (!started) {
            ctx.moveTo(screenX, screenY);
            started = true;
          } else {
            ctx.lineTo(screenX, screenY);
          }
        }
        ctx.strokeStyle = rgbaColor(lineColor, 0.05 + uniformValues.intensity * 0.14);
        ctx.lineWidth = 0.6 + (index % 5 === 0 ? 0.6 : 0);
        ctx.stroke();
  
        for (let particleIndex = 0; particleIndex < line.particles.length; particleIndex += 1) {
          const particleT = (line.particles[particleIndex] + time * (0.18 + uniformValues.pulseSpeed * 0.08)) % 1;
          const latitude = particleT * (Math.PI / 2.15);
          const x = Math.sin(latitude) * Math.cos(longitude);
          const y = Math.cos(latitude);
          const z = Math.sin(latitude) * Math.sin(longitude);
          if (z < -0.3) continue;
          const scale = 0.55 + z * 0.45;
          const screenX = cx + x * radius * scale;
          const screenY = cy - y * radius * scale * 0.72;
          ctx.fillStyle = rgbaColor(particleColor, 0.12 + uniformValues.intensity * 0.24);
          ctx.beginPath();
          ctx.arc(screenX, screenY, 0.9 + scale * 1.4, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, particleColor);
      ctx.restore();
    }
  
    function renderAmbientStarfieldWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - webglStartTime) * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, stars: [] };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const starColor = mixColor({ r: 96, g: 255, b: 180 }, uniformValues.tint, 0.72);
      const warmColor = mixColor({ r: 245, g: 180, b: 90 }, uniformValues.tint, 0.32);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, width * 0.5 + state.pointerX * width * 0.05, height * 0.08, Math.max(width, height) * 0.34, starColor, 0.05 + uniformValues.intensity * 0.06, 0.62);
      drawGlow(ctx, width * 0.9, height * 0.9, Math.max(width, height) * 0.26, warmColor, 0.04 + uniformValues.intensity * 0.05, 0.9);
  
      const visibleCount = Math.round(260 + uniformValues.lineSpread * 260);
      for (let index = 0; index < visibleCount; index += 1) {
        const star = state.stars[index];
        const depth = (((star.z - time * (0.08 + uniformValues.pulseSpeed * 0.06) * star.speed) % 1) + 1) % 1;
        const safeDepth = Math.max(depth, 0.035);
        const x = width * 0.5 + ((star.x + state.pointerX * 0.24 * uniformValues.mouseInfluence) / (safeDepth * 2)) * width * 0.18;
        const y = height * 0.5 + ((star.y + state.pointerY * 0.18 * uniformValues.mouseInfluence) / (safeDepth * 2)) * height * 0.18;
        if (x < -8 || x > width + 8 || y < -8 || y > height + 8) continue;
        const twinkle = 0.78 + (Math.sin(time * 2.2 + star.twinkle) + 1) * 0.11;
        const alpha = clamp((1 - safeDepth) * (0.16 + uniformValues.intensity * 0.42) * twinkle, 0.04, 0.86);
        const radius = clamp((1 - safeDepth) * (0.65 + uniformValues.lineSpread) * star.size + 0.15, 0.35, 2.6);
        if (radius > 1.05) {
          ctx.fillStyle = rgbaColor(starColor, alpha * 0.18);
          ctx.beginPath();
          ctx.arc(x, y, radius * 2.2, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = rgbaColor(starColor, alpha);
        ctx.beginPath();
        ctx.arc(x, y, radius, 0, Math.PI * 2);
        ctx.fill();
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, starColor);
      ctx.restore();
    }
  
    function renderTerrainMeshWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - webglStartTime) * 0.001 * 0.9 * uniformValues.pulseSpeed;
      const state = sceneState || { pointerX: 0, pointerY: 0 };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const lineCount = Math.round(24 + uniformValues.lineSpread * 16);
      const points = Math.round(36 + uniformValues.lineSpread * 22);
      const meshColor = mixColor({ r: 168, g: 162, b: 158 }, uniformValues.tint, 0.48);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.translate(0, -height * 0.08 + state.pointerY * height * 0.03 * uniformValues.mouseInfluence);
      ctx.strokeStyle = rgbaColor(meshColor, 0.1 + uniformValues.intensity * 0.16);
      ctx.lineWidth = 0.7 + uniformValues.intensity * 0.4;
  
      for (let lineIndex = 0; lineIndex <= lineCount; lineIndex += 1) {
        ctx.beginPath();
        for (let pointIndex = 0; pointIndex <= points; pointIndex += 1) {
          const x = (pointIndex / points) * width;
          const yBase = height * 0.18 + (lineIndex / Math.max(lineCount, 1)) * height * 0.92;
          const wave1 = Math.sin(x * 0.003 + time + lineIndex * 0.11 + state.pointerX * 0.8) * (22 + uniformValues.intensity * 22);
          const wave2 = Math.sin(x * 0.007 - time * 0.8) * (10 + uniformValues.intensity * 12);
          const wave3 = Math.cos(lineIndex * 0.18 + time * 1.1 + state.pointerY * 0.7) * (10 + uniformValues.intensity * 8);
          const perspectiveShift = ((lineIndex / Math.max(lineCount, 1)) - 0.5) * state.pointerX * width * 0.07 * uniformValues.mouseInfluence;
          const y = yBase + wave1 + wave2 + wave3;
          if (pointIndex === 0) ctx.moveTo(x + perspectiveShift, y);
          else ctx.lineTo(x + perspectiveShift, y);
        }
        ctx.stroke();
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, meshColor);
      ctx.restore();
    }
  
    function renderSoundBarsWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - webglStartTime) * 0.001 * (1.15 + uniformValues.pulseSpeed * 0.35);
      const state = sceneState || { pointerX: 0, pointerY: 0, detail: [] };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const count = Math.round(44 + uniformValues.lineSpread * 60);
      const barWidth = width / Math.max(count, 1);
      const barColor = mixColor({ r: 17, g: 17, b: 17 }, uniformValues.tint, 0.54);
      const reflectionColor = mixColor({ r: 204, g: 204, b: 204 }, uniformValues.tint, 0.32);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
  
      for (let index = 0; index < count; index += 1) {
        const x = index * barWidth;
        const center = (index / Math.max(count - 1, 1)) * 2 - 1;
        const envelope = Math.max(0, 1 - Math.abs(center) * 1.25);
        const noise1 = Math.sin(index * 0.22 + time * 1.8) * Math.cos(index * 0.11 + time * 0.8);
        const noise2 = Math.sin(index * 0.45 - time * 1.35) * 0.5;
        const noise3 = state.detail[index % state.detail.length];
        const scaleY = Math.max(0.08, Math.abs(noise1 + noise2 + noise3) * (0.22 + uniformValues.intensity * 0.42) * envelope);
        const barHeight = scaleY * height * 0.6;
        const skew = state.pointerX * uniformValues.mouseInfluence * width * 0.03;
        const yShift = -state.pointerY * uniformValues.mouseInfluence * height * 0.03;
        ctx.fillStyle = rgbaColor(barColor, 0.7 + uniformValues.intensity * 0.2);
        ctx.fillRect(x + skew, height * 0.5 - barHeight + yShift, Math.max(1, barWidth * 0.62), barHeight);
        ctx.fillStyle = rgbaColor(reflectionColor, 0.09 + uniformValues.intensity * 0.12);
        ctx.fillRect(x + skew, height * 0.5 + 4 + yShift, Math.max(1, barWidth * 0.62), barHeight * 0.58);
      }
  
      drawGrain(ctx, width, height, time, uniformValues.grain, reflectionColor);
      ctx.restore();
    }
  
    function renderTopologyDotsWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const time = Math.max(0, now - webglStartTime) * 0.001 * (0.95 + uniformValues.pulseSpeed * 0.45);
      const state = sceneState || { pointerX: 0, pointerY: 0 };
      updateScenePointer(state, mouseState, width, height, 0.04);
      const step = Math.max(10, Math.round(22 - uniformValues.lineSpread * 10));
      const dotColor = mixColor({ r: 96, g: 165, b: 250 }, uniformValues.tint, 0.72);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      for (let x = 0; x <= width; x += step) {
        for (let y = 0; y <= height; y += step) {
          const waveX = Math.sin(x * 0.01 + time + state.pointerX * 0.9) * (18 + uniformValues.intensity * 26);
          const waveY = Math.cos(y * 0.01 + time * 0.7 + state.pointerY * 0.8) * (16 + uniformValues.intensity * 22);
          const targetY = height * 0.5 + waveX + waveY;
          const distance = Math.abs(y - targetY);
          const radius = Math.max(0.4, 2.6 - distance * (0.011 + uniformValues.lineSpread * 0.004));
          const alpha = Math.max(0.04, 0.8 - distance * (0.0038 - uniformValues.lineSpread * 0.0005));
          if (alpha <= 0.04 && radius <= 0.5) continue;
          const screenX = x + state.pointerX * 7 * uniformValues.mouseInfluence;
          const screenY = y + state.pointerY * 6 * uniformValues.mouseInfluence;
          ctx.fillStyle = rgbaColor(dotColor, alpha);
          ctx.beginPath();
          ctx.arc(screenX, screenY, radius, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      drawGrain(ctx, width, height, time, uniformValues.grain, dotColor);
      ctx.restore();
    }
  
    function renderRadialBurstWebgl(ctx, width, height, now, uniformValues, mouseState, sceneState) {
      const elapsedMilliseconds = Math.max(0, now - webglStartTime);
      const elapsedSeconds = elapsedMilliseconds * 0.001;
      const state = sceneState || { pointerX: 0, pointerY: 0, lines: [] };
      updateScenePointer(state, mouseState, width, height, 0.05);
      const lineCount = Math.round(170 + uniformValues.lineSpread * 150);
      while (state.lines.length < lineCount) {
        state.lines.push({
          angle: Math.random() * Math.PI * 2,
          speed: 0.00022 + Math.random() * 0.0005,
          lengthOffset: Math.random(),
          colorOffset: Math.random(),
          widthOffset: Math.random(),
          alphaOffset: Math.random()
        });
      }
  
      const centerX = width * 0.5 + state.pointerX * width * 0.06 * uniformValues.mouseInfluence;
      const centerY = height * 0.5 + state.pointerY * height * 0.045 * uniformValues.mouseInfluence;
      const maxRadius = Math.max(width, height) * (0.55 + uniformValues.intensity * 0.32);
      const innerRadius = Math.max(18, Math.min(width, height) * (0.09 + (1 - uniformValues.lineSpread) * 0.05));
      const primaryColor = mixColor({ r: 59, g: 130, b: 246 }, uniformValues.tint, 0.45);
      const accentColor = mixColor({ r: 139, g: 92, b: 246 }, uniformValues.tint, 0.35);
  
      ctx.clearRect(0, 0, width, height);
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      drawGlow(ctx, centerX, centerY, maxRadius * 0.42, uniformValues.tint, 0.08 + uniformValues.intensity * 0.08, 1);
  
      for (let index = 0; index < lineCount; index += 1) {
        const line = state.lines[index];
        line.angle += line.speed * (0.75 + uniformValues.pulseSpeed * 0.55);
        const currentAngle = line.angle + state.pointerX * 0.08 * uniformValues.mouseInfluence;
        const pulse = Math.sin(elapsedMilliseconds * 0.0021 + line.lengthOffset * Math.PI * 2) * 0.2 + 0.82;
        const length = maxRadius * (0.62 + pulse * (0.24 + uniformValues.intensity * 0.22));
        const startX = centerX + Math.cos(currentAngle) * innerRadius;
        const startY = centerY + Math.sin(currentAngle) * innerRadius;
        const endX = centerX + Math.cos(currentAngle) * length;
        const endY = centerY + Math.sin(currentAngle) * length;
        const lineColor = line.colorOffset > 0.5 ? primaryColor : accentColor;
        const opacityBase = 0.08 + uniformValues.intensity * 0.22 + line.alphaOffset * 0.12;
        const opacity = opacityBase * (0.75 + Math.sin(elapsedMilliseconds * 0.0012 + line.alphaOffset * Math.PI * 2) * 0.25);
        const gradient = ctx.createLinearGradient(startX, startY, endX, endY);
        gradient.addColorStop(0, rgbaColor(lineColor, 0));
        gradient.addColorStop(0.18, rgbaColor(lineColor, opacity));
        gradient.addColorStop(0.82, rgbaColor(lineColor, opacity * 0.52));
        gradient.addColorStop(1, rgbaColor(lineColor, 0));
        ctx.strokeStyle = gradient;
        ctx.lineWidth = 1 + line.widthOffset * (1.2 + uniformValues.intensity * 1.1);
        ctx.beginPath();
        ctx.moveTo(startX, startY);
        ctx.lineTo(endX, endY);
        ctx.stroke();
      }
      drawGrain(ctx, width, height, elapsedSeconds, uniformValues.grain, accentColor);
      ctx.restore();
    }
  
    function renderWebglOverlayFrame(targetCtx, width, height, now, uniformValues, mouseState) {
      webglOverlayShared.renderCanvasOverlayFrame(
        targetCtx,
        width,
        height,
        now,
        webglStartTime,
        uniformValues,
        mouseState,
        ensureWebglSceneState(uniformValues.overlayType)
      );
    }
  
    function blendWebglIntoData(data, width, height, now, uniformValues) {
      if (!data || !isWebglAsciiFxEnabled()) return;
      webglSampleCanvas.width = Math.max(1, width);
      webglSampleCanvas.height = Math.max(1, height);
      webglSampleCtx.setTransform(1, 0, 0, 1, 0, 0);
      webglSampleCtx.clearRect(0, 0, width, height);
      if (usesShaderOverlay(uniformValues)) {
        syncShaderCanvasSize(width, height, 1);
        renderShaderOverlayFrame(width, height, now, uniformValues);
        webglSampleCtx.drawImage(webglShaderCanvas, 0, 0, width, height);
      } else {
        renderWebglOverlayFrame(
          webglSampleCtx,
          width,
          height,
          now,
          uniformValues,
          getWebglMouseState(width, height)
        );
      }
      const overlayData = webglSampleCtx.getImageData(0, 0, width, height).data;
      for (let index = 0; index < data.length; index += 4) {
        const alpha = (overlayData[index + 3] / 255) * uniformValues.opacity;
        if (alpha <= 0.001) continue;
        const nextRed = 255 - ((255 - data[index]) * (255 - overlayData[index])) / 255;
        const nextGreen = 255 - ((255 - data[index + 1]) * (255 - overlayData[index + 1])) / 255;
        const nextBlue = 255 - ((255 - data[index + 2]) * (255 - overlayData[index + 2])) / 255;
        data[index] = Math.round(data[index] + (nextRed - data[index]) * alpha);
        data[index + 1] = Math.round(data[index + 1] + (nextGreen - data[index + 1]) * alpha);
        data[index + 2] = Math.round(data[index + 2] + (nextBlue - data[index + 2]) * alpha);
        data[index + 3] = 255;
      }
    }
  
    function getRetroDuotonePalette() {
      const key = String(SETTINGS.retroDuotone || 'amber-classic');
      return RETRO_DUOTONE_PALETTES[key] || RETRO_DUOTONE_PALETTES['amber-classic'];
    }
  
    function selectCharset() {
      if (SETTINGS.style === 'letters') {
        const legacySet = String(SETTINGS.letterSet || 'alphabet').toLowerCase();
        return CHARSETS['letters-' + legacySet] || CHARSETS['letters-alphabet'];
      }
      if (SETTINGS.style === 'braille') return BRAILLE_VARIANTS[SETTINGS.brailleVariant] || BRAILLE_VARIANTS.standard;
      if (SETTINGS.style === 'claude') return CHARSETS.blocks;
      if (SETTINGS.style === 'halftone') return HALFTONE_CHARS;
      if (SETTINGS.style === 'retro' || SETTINGS.style === 'winamp') return RETRO_CHARS;
      if (SETTINGS.style === 'terminal') {
        const key = String(SETTINGS.terminalCharset || 'binary');
        return TERMINAL_CHARSET_PRESETS[key] || TERMINAL_CHARSET_PRESETS.binary;
      }
      if (SETTINGS.style === 'classic' && SETTINGS.charset === 'custom') {
        const customSet = typeof SETTINGS.customCharset === 'string'
          ? SETTINGS.customCharset.slice(0, 100)
          : '';
        return customSet.length > 0 ? customSet : CHARSETS.standard;
      }
      if (SETTINGS.style === 'matrix') return MATRIX_CHARS;
      return CHARSETS[SETTINGS.charset] || CHARSETS.standard;
    }
  
    function getLocalEdgeContrast(values, x, y, cols, rows) {
      const idx = y * cols + x;
      const center = values[idx] ?? 0;
      const left = x > 0 ? values[idx - 1] ?? center : center;
      const right = x + 1 < cols ? values[idx + 1] ?? center : center;
      const up = y > 0 ? values[idx - cols] ?? center : center;
      const down = y + 1 < rows ? values[idx + cols] ?? center : center;
      const gradientX = Math.abs(right - left);
      const gradientY = Math.abs(down - up);
      return clamp((gradientX + gradientY) / 510, 0, 1);
    }
  
    function getBackgroundDitherColor(r, g, b, gray) {
      if (SETTINGS.style === 'claude') {
        const intensity = clamp(gray + 30, 0, 255);
        return {
          r: clamp(Math.floor(intensity * 1.02), 0, 255),
          g: clamp(Math.floor(intensity * 0.52), 0, 255),
          b: clamp(Math.floor(intensity * 0.1), 0, 255),
        };
      }
      if (SETTINGS.style === 'terminal') {
        const phosphor = clamp(gray + 28, 0, 255);
        return {
          r: clamp(Math.floor(phosphor * 0.14), 0, 96),
          g: phosphor,
          b: clamp(Math.floor(phosphor * 0.24), 0, 116),
        };
      }
      if (SETTINGS.style === 'retro' || SETTINGS.style === 'winamp') {
        const palette = getRetroDuotonePalette();
        const sepia = clamp(Math.floor(gray * 1.04 + 12), 0, 255);
        const tone = clamp(Math.pow(sepia / 255, 0.94), 0, 1);
        return {
          r: lerpChannel(palette.low.r, palette.high.r, tone),
          g: lerpChannel(palette.low.g, palette.high.g, tone),
          b: lerpChannel(palette.low.b, palette.high.b, tone),
        };
      }
      if (SETTINGS.colorMode === 'color') {
        return {
          r: clamp(Math.floor(r), 0, 255),
          g: clamp(Math.floor(g), 0, 255),
          b: clamp(Math.floor(b), 0, 255),
        };
      }
      if (SETTINGS.colorMode === 'green') {
        const intensity = clamp(gray + 20, 0, 255);
        return {
          r: clamp(Math.floor(intensity * 0.2), 0, 255),
          g: intensity,
          b: clamp(Math.floor(intensity * 0.3), 0, 255),
        };
      }
      if (SETTINGS.colorMode === 'amber') {
        const intensity = clamp(gray + 18, 0, 255);
        return {
          r: intensity,
          g: clamp(Math.floor(intensity * 0.72), 0, 255),
          b: clamp(Math.floor(intensity * 0.16), 0, 255),
        };
      }
      if (SETTINGS.colorMode === 'custom') {
        const rawColor = typeof SETTINGS.customColor === 'string' ? SETTINGS.customColor.trim() : '';
        const match = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(rawColor);
        const hex =
          match && match[1].length === 3
            ? match[1].split('').map((char) => char + char).join('')
            : match
              ? match[1]
              : 'ffffff';
        const baseR = parseInt(hex.slice(0, 2), 16);
        const baseG = parseInt(hex.slice(2, 4), 16);
        const baseB = parseInt(hex.slice(4, 6), 16);
        const intensity = gray / 255;
        return {
          r: clamp(Math.floor(baseR * intensity), 0, 255),
          g: clamp(Math.floor(baseG * intensity), 0, 255),
          b: clamp(Math.floor(baseB * intensity), 0, 255),
        };
      }
      return { r: gray, g: gray, b: gray };
    }
  
    function getBorderGlowColor() {
      if (SETTINGS.style === 'terminal') return { r: 96, g: 255, b: 164 };
      if (SETTINGS.style === 'claude') return { r: 255, g: 186, b: 118 };
      if (SETTINGS.style === 'retro' || SETTINGS.style === 'winamp') {
        const palette = getRetroDuotonePalette();
        return { ...palette.high };
      }
      if (SETTINGS.colorMode === 'green') return { r: 110, g: 255, b: 175 };
      if (SETTINGS.colorMode === 'amber') return { r: 255, g: 192, b: 118 };
      if (SETTINGS.colorMode === 'custom') {
        const rawColor = typeof SETTINGS.customColor === 'string' ? SETTINGS.customColor.trim() : '';
        const match = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(rawColor);
        const hex = match ? (match[1].length === 3 ? match[1].split('').map((char) => char + char).join('') : match[1]) : 'ffffff';
        return {
          r: parseInt(hex.slice(0, 2), 16),
          g: parseInt(hex.slice(2, 4), 16),
          b: parseInt(hex.slice(4, 6), 16),
        };
      }
      if (SETTINGS.colorMode === 'color') return { r: 176, g: 214, b: 255 };
      return { r: 255, g: 255, b: 255 };
    }
  
    function drawBorderGlowOverlay(ctx, width, height, strength) {
      const glowStrength = clamp(Number(strength ?? 0) || 0, 0, 1);
      if (!ctx || width <= 0 || height <= 0 || glowStrength <= 0.001) return;
      const glowColor = getBorderGlowColor();
      const shortestEdge = Math.max(1, Math.min(width, height));
      const glowSize = Math.max(10, shortestEdge * (0.055 + glowStrength * 0.24));
      const edgeAlpha = clamp(0.018 + glowStrength * 0.34, 0, 0.62);
      const cornerRadius = glowSize * 1.35;
      const edgeColor = (alpha) =>
        applyOutputPolarity(
          'rgba(' + glowColor.r + ', ' + glowColor.g + ', ' + glowColor.b + ', ' + clamp(alpha, 0, 1).toFixed(3) + ')'
        );
  
      ctx.save();
      ctx.globalCompositeOperation = SETTINGS.themeOutputInvert ? 'multiply' : 'screen';
      ctx.globalAlpha = 1;
  
      const top = ctx.createLinearGradient(0, 0, 0, glowSize);
      top.addColorStop(0, edgeColor(edgeAlpha * 1.12));
      top.addColorStop(0.58, edgeColor(edgeAlpha * 0.44));
      top.addColorStop(1, edgeColor(0));
      ctx.fillStyle = top;
      ctx.fillRect(0, 0, width, glowSize);
  
      const bottom = ctx.createLinearGradient(0, height, 0, height - glowSize);
      bottom.addColorStop(0, edgeColor(edgeAlpha * 1.12));
      bottom.addColorStop(0.58, edgeColor(edgeAlpha * 0.44));
      bottom.addColorStop(1, edgeColor(0));
      ctx.fillStyle = bottom;
      ctx.fillRect(0, height - glowSize, width, glowSize);
  
      const left = ctx.createLinearGradient(0, 0, glowSize, 0);
      left.addColorStop(0, edgeColor(edgeAlpha));
      left.addColorStop(0.58, edgeColor(edgeAlpha * 0.4));
      left.addColorStop(1, edgeColor(0));
      ctx.fillStyle = left;
      ctx.fillRect(0, 0, glowSize, height);
  
      const right = ctx.createLinearGradient(width, 0, width - glowSize, 0);
      right.addColorStop(0, edgeColor(edgeAlpha));
      right.addColorStop(0.58, edgeColor(edgeAlpha * 0.4));
      right.addColorStop(1, edgeColor(0));
      ctx.fillStyle = right;
      ctx.fillRect(width - glowSize, 0, glowSize, height);
  
      const cornerAlpha = edgeAlpha * 0.9;
      const drawCorner = (x, y) => {
        const radial = ctx.createRadialGradient(x, y, 0, x, y, cornerRadius);
        radial.addColorStop(0, edgeColor(cornerAlpha));
        radial.addColorStop(0.65, edgeColor(cornerAlpha * 0.28));
        radial.addColorStop(1, edgeColor(0));
        ctx.fillStyle = radial;
        ctx.fillRect(x - cornerRadius, y - cornerRadius, cornerRadius * 2, cornerRadius * 2);
      };
      drawCorner(0, 0);
      drawCorner(width, 0);
      drawCorner(0, height);
      drawCorner(width, height);
      ctx.restore();
    }
  
    function charFromGray(gray, charset, x, y, cols, rows, edgeContrast = 0) {
      const normalized = gray / 255;
      if (SETTINGS.style === 'halftone') {
        const dotRamp = HALFTONE_CHARS;
        const screen =
          (Math.sin((x * 0.82 + y * 0.33) * 1.55) + Math.cos((x * 0.27 - y * 0.94) * 1.25) + 2) * 0.25;
        const adjusted = clamp(Math.pow(normalized, 0.9) * 0.8 + screen * 0.2, 0, 1);
        const idx = Math.floor(adjusted * (dotRamp.length - 1));
        return dotRamp[clamp(idx, 0, dotRamp.length - 1)];
      }
      if (SETTINGS.style === 'braille') {
        const variant = String(SETTINGS.brailleVariant || 'standard');
        const variantBias = variant === 'dense' ? 0.11 : variant === 'sparse' ? -0.08 : 0;
        const screen =
          (Math.sin((x * 0.73 + y * 0.41) * 1.37) + Math.cos((x * 0.29 - y * 0.88) * 1.11) + 2) * 0.25;
        const concentration = clamp(edgeContrast * 1.55 + Math.max(0, normalized - 0.45) * 0.28, 0, 1);
        const adjusted = clamp(
          Math.pow(normalized, 0.88) * 0.82 + screen * 0.11 + concentration * 0.24 + variantBias,
          0,
          1
        );
        const idx = Math.floor(adjusted * (charset.length - 1));
        return charset[clamp(idx, 0, charset.length - 1)];
      }
      if (SETTINGS.style === 'dotcross') {
        const dotRamp = '  .·:oO';
        const crossRamp = '  ·+xX#';
        const screen =
          (Math.sin((x * 0.82 + y * 0.33) * 1.55) + Math.cos((x * 0.27 - y * 0.94) * 1.25) + 2) * 0.25;
        const adjusted = clamp(Math.pow(normalized, 0.9) * 0.82 + screen * 0.18, 0, 1);
        const dotIdx = Math.floor(adjusted * (dotRamp.length - 1));
        const crossIdx = Math.floor(adjusted * (crossRamp.length - 1));
        const edgeMix = clamp(edgeContrast * 1.4 + Math.max(0, adjusted - 0.5) * 0.22, 0, 1);
        const weave =
          (Math.sin((x + 1) * 1.71 + (y + 1) * 2.37) + Math.cos((x + 1) * 0.83 - (y + 1) * 1.29) + 2) * 0.25;
        const useCross = edgeMix > clamp(0.46 + weave * 0.28, 0, 1);
        const glyph = useCross
          ? crossRamp[clamp(crossIdx, 0, crossRamp.length - 1)]
          : dotRamp[clamp(dotIdx, 0, dotRamp.length - 1)];
        return glyph || ' ';
      }
      if (SETTINGS.style === 'particles') {
        const density = clamp(SETTINGS.particleDensity ?? 0.5, 0.05, 1);
        const nx = cols > 1 ? (x / (cols - 1)) * 2 - 1 : 0;
        const ny = rows > 1 ? (y / (rows - 1)) * 2 - 1 : 0;
        const center = 1 - clamp(Math.sqrt(nx * nx + ny * ny), 0, 1);
        const centerBias = Math.pow(center, 1.35) * density * 0.42;
        const edgeBoost = clamp(edgeContrast * 1.6 + Math.max(0, normalized - 0.45) * 0.24, 0, 1);
        const grain = (Math.sin((x + 1) * 12.9898 + (y + 1) * 78.233) + 1) * 0.5;
        const jitter = (grain - 0.5) * (0.18 - density * 0.08);
        const brightnessBias = clamp((SETTINGS.brightness ?? 0) / 50, -1, 1) * 0.12;
        const threshold = clamp(
          1 - density - centerBias * 0.95 - edgeBoost * 0.42 + jitter * 0.9 - brightnessBias * 0.25,
          0.01,
          0.95
        );
        const fillBias = Math.pow(normalized, 0.82) * 0.18 + edgeBoost * 0.15 + Math.max(0, brightnessBias) * 0.1;
        return normalized + fillBias >= threshold ? (SETTINGS.particleChar || '*') : ' ';
      }
      let adjusted = normalized;
      if (SETTINGS.style === 'retro' || SETTINGS.style === 'winamp') {
        const retroNoise = clamp(Number(SETTINGS.retroNoise ?? 0.45) || 0, 0, 1);
        const grain = (Math.sin((x + 1) * 12.9898 + (y + 1) * 78.233) + 1) * 0.5;
        const jitter = (grain - 0.5) * retroNoise * 0.22;
        adjusted = clamp(Math.pow(normalized, 0.78) + jitter, 0, 1);
        const bands = 10 + Math.round(retroNoise * 16);
        adjusted = Math.round(adjusted * bands) / Math.max(1, bands);
      }
      if (SETTINGS.style === 'terminal') adjusted = Math.pow(normalized, 0.82);
      if (SETTINGS.style === 'matrix') adjusted = Math.pow(normalized, 0.7);
      const idx = Math.floor(adjusted * (charset.length - 1));
      return charset[clamp(idx, 0, charset.length - 1)];
    }
  
    function colorFromMode(r, g, b, gray, x, y, cols, rows, edgeContrast = 0) {
      let particleBoost = 0;
      let particleColorGain = 1;
      if (SETTINGS.style === 'particles') {
        const density = clamp(SETTINGS.particleDensity ?? 0.5, 0.05, 1);
        const nx = cols > 1 ? (x / (cols - 1)) * 2 - 1 : 0;
        const ny = rows > 1 ? (y / (rows - 1)) * 2 - 1 : 0;
        const center = 1 - clamp(Math.sqrt(nx * nx + ny * ny), 0, 1);
        const centerGlow = Math.pow(center, 1.4) * density;
        const edgeGlow = clamp(edgeContrast, 0, 1);
        particleBoost = centerGlow * (24 + density * 72) + edgeGlow * (18 + density * 34);
        particleColorGain = 1 + centerGlow * 0.45 + edgeGlow * 0.22;
      }
      const boostedGray = clamp(gray + particleBoost, 0, 255);
  
      if (SETTINGS.style === 'claude') {
        const intensity = clamp(gray + 36, 0, 255);
        const red = clamp(Math.floor(intensity * 1.03), 0, 255);
        const green = clamp(Math.floor(intensity * 0.5), 0, 255);
        const blue = clamp(Math.floor(intensity * 0.08), 0, 255);
        return 'rgb(' + red + ', ' + green + ', ' + blue + ')';
      }
  
      if (SETTINGS.style === 'retro' || SETTINGS.style === 'winamp') {
        const retroNoise = clamp(Number(SETTINGS.retroNoise ?? 0.45) || 0, 0, 1);
        const palette = getRetroDuotonePalette();
        const nx = cols > 1 ? (x / (cols - 1)) * 2 - 1 : 0;
        const ny = rows > 1 ? (y / (rows - 1)) * 2 - 1 : 0;
        const vignette = 1 - clamp(Math.sqrt(nx * nx + ny * ny), 0, 1) * 0.32;
        const grain = Math.sin((x + 1) * 12.9898 + (y + 1) * 78.233);
        const shimmer = Math.sin(x * 0.13 + y * 0.07) * 5;
        const noise = Math.sin((x + 1) * 41.13 + (y + 1) * 17.37 + gray * 0.031);
        const warm = clamp(
          gray * 1.06 + 14 + shimmer + grain * (3 + retroNoise * 7.5) + noise * (1 + retroNoise * 16),
          0,
          255
        );
        const tone = clamp(Math.pow((warm * vignette) / 255, 0.86), 0, 1);
        const red = lerpChannel(palette.low.r, palette.high.r, tone);
        const green = lerpChannel(palette.low.g, palette.high.g, tone);
        const blue = lerpChannel(palette.low.b, palette.high.b, tone);
        return 'rgb(' + red + ', ' + green + ', ' + blue + ')';
      }
  
      if (SETTINGS.style === 'terminal') {
        const phosphor = clamp(gray + 32, 0, 255);
        const scanShade = ((x + y) & 1) === 0 ? 1 : 0.84;
        const green = clamp(Math.floor(phosphor * scanShade), 0, 255);
        const red = clamp(Math.floor(green * 0.12), 0, 72);
        const blue = clamp(Math.floor(green * 0.2), 0, 88);
        return 'rgb(' + red + ', ' + green + ', ' + blue + ')';
      }
  
      if (SETTINGS.colorMode === 'color') {
        const boostedR = clamp(Math.floor(r * particleColorGain + particleBoost * 0.22), 0, 255);
        const boostedG = clamp(Math.floor(g * particleColorGain + particleBoost * 0.28), 0, 255);
        const boostedB = clamp(Math.floor(b * particleColorGain + particleBoost * 0.2), 0, 255);
        return 'rgb(' + boostedR + ', ' + boostedG + ', ' + boostedB + ')';
      }
  
      if (SETTINGS.colorMode === 'green') {
        const intensity = clamp(boostedGray + 25, 0, 255);
        return 'rgb(' + Math.floor(intensity * 0.2) + ', ' + intensity + ', ' + Math.floor(intensity * 0.3) + ')';
      }
  
      if (SETTINGS.colorMode === 'amber') {
        const intensity = clamp(boostedGray + 20, 0, 255);
        return 'rgb(' + intensity + ', ' + Math.floor(intensity * 0.7) + ', ' + Math.floor(intensity * 0.15) + ')';
      }
  
      if (SETTINGS.colorMode === 'custom') {
        const rawColor = typeof SETTINGS.customColor === 'string' ? SETTINGS.customColor.trim() : '';
        const match = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/.exec(rawColor);
        const hex = match ? (match[1].length === 3 ? match[1].split('').map((char) => char + char).join('') : match[1]) : 'ffffff';
        const baseR = parseInt(hex.slice(0, 2), 16);
        const baseG = parseInt(hex.slice(2, 4), 16);
        const baseB = parseInt(hex.slice(4, 6), 16);
        const intensity = boostedGray / 255;
        const red = clamp(Math.floor(baseR * intensity), 0, 255);
        const green = clamp(Math.floor(baseG * intensity), 0, 255);
        const blue = clamp(Math.floor(baseB * intensity), 0, 255);
        return 'rgb(' + red + ', ' + green + ', ' + blue + ')';
      }
  
      return 'rgb(' + boostedGray + ', ' + boostedGray + ', ' + boostedGray + ')';
    }
  
    function applyOverlayFx(gray, x, y, cols, rows, timeSeconds) {
      const preset = SETTINGS.overlayPreset || 'none';
      const strength = clamp(SETTINGS.overlayStrength ?? 0.4, 0, 1);
      if (preset === 'none' || strength <= 0) return gray;
  
      if (preset === 'noise') {
        const scale = clamp(SETTINGS.noiseScale ?? 24, 4, 120);
        const speed = clamp(SETTINGS.noiseSpeed ?? 1, 0, 4);
        const projection = getDirectionProjection(SETTINGS.noiseDirection || 'right');
        const { primaryNorm, secondaryNorm } = projectDirection(x, y, cols, rows, projection);
        const flowSpan = Math.max(cols, rows);
        const phase = timeSeconds * speed * 2.4;
        const axisPrimary = (primaryNorm * flowSpan + 17.3) / scale;
        const axisSecondary = (secondaryNorm * flowSpan - 9.7) / scale;
        const coherent = Math.sin(axisPrimary + phase) * Math.cos(axisSecondary - phase * 0.73);
        const grain = Math.sin(primaryNorm * flowSpan * 1.37 + secondaryNorm * flowSpan * 2.11 + phase * 6.2);
        const amount = 16 + strength * 72;
        return clamp(gray + (coherent * 0.65 + grain * 0.35) * amount, 0, 255);
      }
  
      if (preset === 'intervals' || preset === 'lines') {
        const spacing = clamp(SETTINGS.intervalSpacing ?? 12, 4, 64);
        const speed = clamp(SETTINGS.intervalSpeed ?? 1, 0, 4);
        const width = clamp(SETTINGS.intervalWidth ?? 2, 1, 8);
        const projection = getDirectionProjection(SETTINGS.intervalDirection || 'down');
        const { primaryNorm, secondaryNorm } = projectDirection(x, y, cols, rows, projection);
        const flowSpan = Math.max(cols, rows);
        const axisCoord = primaryNorm * flowSpan;
        const crossCoord = secondaryNorm * flowSpan;
        const offsetRaw = timeSeconds * speed * spacing * 1.7;
        const offset = ((offsetRaw % spacing) + spacing) % spacing;
        const phase = (axisCoord + offset) % spacing;
        const distance = Math.min(phase, spacing - phase);
        const lineMask = 1 - clamp(distance / width, 0, 1);
        const wave =
          Math.sin((axisCoord / spacing) * Math.PI * 2 + timeSeconds * speed * 1.8 + (crossCoord / Math.max(flowSpan, 1)) * 1.1);
        const amount = strength * 88;
        return clamp(gray + lineMask * amount * 0.85 + wave * amount * 0.32, 0, 255);
      }
  
      if (preset === 'beam') {
        const speed = 0.45 + strength * 2.2;
        const width = 0.08 + strength * 0.22;
        const projection = getDirectionProjection(SETTINGS.beamDirection || 'right');
        const { primaryNorm } = projectDirection(x, y, cols, rows, projection);
        const sweepRaw = (timeSeconds * speed) % 1.2;
        const center = ((sweepRaw + 1.2) % 1.2) - 0.1;
        const distance = Math.abs(primaryNorm - center);
        const beam = Math.max(0, 1 - distance / width);
        return clamp(gray + beam * (34 + strength * 120), 0, 255);
      }
  
      if (preset === 'glitch') {
        const projection = getDirectionProjection(SETTINGS.glitchDirection || 'right');
        const { primaryNorm, secondaryNorm } = projectDirection(x, y, cols, rows, projection);
        const flowSpan = Math.max(cols, rows);
        const secondaryCoord = secondaryNorm * flowSpan;
        const laneHeight = 2 + Math.floor((1 - strength) * 3);
        const lane = Math.floor(secondaryCoord / laneHeight);
        const windowTick = Math.floor(timeSeconds * (0.75 + strength * 1.35));
        const laneChance = (Math.sin((lane + 1) * 19.73 + windowTick * 7.11) + 1) * 0.5;
        const laneActive = laneChance > 0.74 ? 1 : 0;
        const laneSpeed =
          0.12 + ((Math.sin((lane + 1) * 6.37) + 1) * 0.5) * (0.22 + strength * 0.34);
        const lanePhase = (Math.sin((lane + 1) * 2.91) + 1) * 0.5;
        const head = (timeSeconds * laneSpeed + lanePhase) % 1;
        const trailLength = 0.12 + strength * 0.28;
        const distanceAcross = (primaryNorm - head + 1) % 1;
        const trail = Math.max(0, 1 - distanceAcross / trailLength);
        const scanPulse = Math.max(
          0,
          Math.sin(distanceAcross * Math.PI * (5 + strength * 8) - timeSeconds * (2 + strength * 5))
        );
        const rowGlow = laneActive * (trail * (18 + strength * 86) + scanPulse * (6 + strength * 26));
        const syncTear =
          laneActive *
          Math.sin(primaryNorm * Math.PI * 2 * (2 + strength * 4) - timeSeconds * (1.4 + strength * 2.2)) *
          (3 + strength * 14);
        const staticNoise = Math.sin((x + 1) * 17.7 + (y + 1) * 29.3 + timeSeconds * 9.1) * (1.5 + strength * 4.5);
        return clamp(gray + rowGlow + syncTear + staticNoise + secondaryNorm * 0.5, 0, 255);
      }
  
      if (preset === 'crt') {
        const projection = getDirectionProjection(SETTINGS.crtDirection || 'down');
        const { primaryNorm, secondaryNorm } = projectDirection(x, y, cols, rows, projection);
        const flowSpan = Math.max(cols, rows);
        const primaryCoord = primaryNorm * flowSpan;
        const secondaryCoord = secondaryNorm * flowSpan;
        const nx = (x / Math.max(cols - 1, 1)) * 2 - 1;
        const ny = (y / Math.max(rows - 1, 1)) * 2 - 1;
        const radial = nx * nx * 0.84 + ny * ny * 1.12;
        const curvature = 1 - clamp(radial, 0, 1);
        const edgeFalloff = (1 - curvature) * (24 + strength * 116);
        const scanline = Math.sin((primaryCoord + timeSeconds * (34 + strength * 24)) * Math.PI);
        const triad = Math.sin((secondaryCoord + timeSeconds * 8.5) * 2.9);
        const flicker = Math.sin(timeSeconds * 61) * 0.55 + Math.sin(timeSeconds * 23) * 0.45;
        const rollRaw = (timeSeconds * (0.12 + strength * 0.24)) % 1;
        const rollCenter = (rollRaw + 1) % 1;
        const rollDistance = Math.abs(primaryNorm - rollCenter);
        const rollGlow = Math.max(0, 1 - rollDistance / (0.045 + strength * 0.08));
        const laneToken = Math.sin((secondaryCoord + 1) * 14.37 + Math.floor(timeSeconds * 12) * 1.91);
        const laneActive = laneToken > 0.72 ? 1 : 0;
        const streakRaw = (timeSeconds * (0.55 + strength * 1.35) + secondaryCoord * 0.037) % 1;
        const streakHead = (streakRaw + 1) % 1;
        const streakDistance = Math.abs(primaryNorm - streakHead);
        const streakCore = Math.max(0, 1 - streakDistance / (0.014 + strength * 0.03));
        const streakTicks = Math.max(
          0,
          Math.sin(primaryNorm * 170 - timeSeconds * (28 + strength * 58) + secondaryCoord * 2.4)
        );
        const glitchStreak = laneActive * (streakCore * (8 + strength * 34) + streakTicks * (2 + strength * 10));
        const overdrive = Math.pow(gray / 255, 1.35) * (22 + strength * 72);
        const crush = Math.pow(1 - gray / 255, 1.2) * (8 + strength * 24);
        const boost =
          scanline * (14 + strength * 36) +
          triad * (6 + strength * 14) +
          flicker * (5 + strength * 14) +
          rollGlow * (18 + strength * 64) +
          glitchStreak +
          overdrive -
          crush;
        return clamp(gray + boost - edgeFalloff, 0, 255);
      }
  
      return gray;
    }
  
    function drawError(message) {
      ctx.clearRect(0, 0, renderWidth, renderHeight);
      webglCtx.clearRect(0, 0, renderWidth, renderHeight);
      if (webglShaderGl) {
        webglShaderGl.viewport(0, 0, webglShaderCanvas.width || 1, webglShaderCanvas.height || 1);
        webglShaderGl.clearColor(0, 0, 0, 0);
        webglShaderGl.clear(webglShaderGl.COLOR_BUFFER_BIT);
      }
      ctx.fillStyle = '#fca5a5';
      ctx.font = '16px ' + (SETTINGS.renderFont || 'Helvetica, Arial, sans-serif');
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(message, renderWidth / 2, renderHeight / 2);
    }
  
    function readBounds() {
      const rect = mount.getBoundingClientRect();
      const width = Math.max(1, Math.round(rect.width || mount.clientWidth || window.innerWidth || 1));
      const height = Math.max(1, Math.round(rect.height || mount.clientHeight || window.innerHeight || 1));
      return {
        left: rect.left,
        top: rect.top,
        width,
        height,
        right: rect.left + width,
        bottom: rect.top + height
      };
    }
  
    function resize() {
      bounds = readBounds();
      viewWidth = bounds.width;
      viewHeight = bounds.height;
    }
  
    function parseAspectRatio(aspectValue) {
      if (!aspectValue || aspectValue === 'source') return null;
      const parts = String(aspectValue).split(':');
      if (parts.length !== 2) return null;
      const w = Number(parts[0]);
      const h = Number(parts[1]);
      if (!Number.isFinite(w) || !Number.isFinite(h) || w <= 0 || h <= 0) return null;
      return w / h;
    }
  
    function getSourceSize(element) {
      return {
        width: element.videoWidth || element.naturalWidth || 0,
        height: element.videoHeight || element.naturalHeight || 0
      };
    }
  
    function getCoverCropRect(sourceWidth, sourceHeight, targetAspect) {
      const safeSourceWidth = Math.max(1, Number(sourceWidth) || 1);
      const safeSourceHeight = Math.max(1, Number(sourceHeight) || 1);
      const safeTargetAspect = Math.max(0.0001, Number(targetAspect) || safeSourceWidth / safeSourceHeight);
      const sourceAspect = safeSourceWidth / safeSourceHeight;
      let cropX = 0;
      let cropY = 0;
      let cropWidth = safeSourceWidth;
      let cropHeight = safeSourceHeight;
  
      if (sourceAspect > safeTargetAspect) {
        cropWidth = safeSourceHeight * safeTargetAspect;
        cropX = (safeSourceWidth - cropWidth) * 0.5;
      } else if (sourceAspect < safeTargetAspect) {
        cropHeight = safeSourceWidth / safeTargetAspect;
        cropY = (safeSourceHeight - cropHeight) * 0.5;
      }
  
      return { cropX, cropY, cropWidth, cropHeight };
    }
  
    function proceduralField(x, y, cols, rows, timeSeconds) {
      const nx = cols > 1 ? (x / (cols - 1)) * 2 - 1 : 0;
      const ny = rows > 1 ? (y / (rows - 1)) * 2 - 1 : 0;
      const scale = clamp(SOURCE.proceduralScale ?? 1, 0.45, 2.4);
      const speed = clamp(SOURCE.proceduralSpeed ?? 1, 0.2, 3.5);
      const t = timeSeconds * speed;
      const radius = Math.sqrt(nx * nx + ny * ny);
      const angle = Math.atan2(ny, nx);
      const flow = Math.sin((nx * 3.6 + t * 1.2) * scale);
      const drift = Math.cos((ny * 4.8 - t * 0.9) * scale);
      const ring = Math.sin((radius * 13.5 - t * 2.35 + angle * 2.6) * scale);
      const grain = Math.sin((nx * 18.7 + ny * 11.3 + t * 4.7) * scale);
      return clamp((flow * 0.33 + drift * 0.26 + ring * 0.31 + grain * 0.1 + 1) * 0.5, 0, 1);
    }
  
    function isActiveForRendering() {
      const requiresInView = EXPORT_OPTIONS.pauseWhenOffscreen !== false;
      return isPageVisible && (!requiresInView || isInViewport);
    }
  
    function isPlayableVideoSource(value) {
      return Boolean(value && typeof value.play === 'function' && typeof value.pause === 'function');
    }
  
    function syncSourcePlayback(shouldRun) {
      if (!source || source.kind === 'procedural' || SOURCE.type === 'image') return;
      if (!isPlayableVideoSource(source)) return;
      if (SOURCE.type === 'camera' && stream) {
        const tracks = typeof stream.getVideoTracks === 'function' ? stream.getVideoTracks() : stream.getTracks();
        tracks.forEach((track) => {
          track.enabled = shouldRun;
        });
      }
      if (shouldRun) {
        source.play().catch(() => {});
        return;
      }
      source.pause();
    }
  
    function requiresContinuousRendering(interactionEnabled = Boolean(EXPORT_OPTIONS.enableInteractionEffects)) {
      return (
        SOURCE.type !== 'image' ||
        SETTINGS.overlayPreset !== 'none' ||
        isWebglAsciiFxEnabled() ||
        (interactionEnabled && (pointer.inside || clickBursts.length > 0))
      );
    }
  
    function getTargetFps(interactionEnabled) {
      const maxFps = clamp(Number(EXPORT_OPTIONS.maxFps ?? 30) || 30, 6, 60);
      if (EXPORT_OPTIONS.adaptivePerformance === false) return maxFps;
      const idleFps = clamp(Number(EXPORT_OPTIONS.idleFps ?? 12) || 12, 1, maxFps);
      const isInteractive = interactionEnabled && (pointer.inside || clickBursts.length > 0);
      return isInteractive ? maxFps : idleFps;
    }
  
    function handleRenderActivityChange(forceNextFrame = false) {
      if (!isActiveForRendering()) {
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        if (webglRafId) {
          cancelAnimationFrame(webglRafId);
          webglRafId = null;
        }
        pendingForceRender = false;
        pointer = { ...pointer, inside: false };
        if (clickBursts.length) clickBursts = [];
        syncSourcePlayback(false);
        reportFps(0);
        return;
      }
  
      syncSourcePlayback(true);
      scheduleSeparateWebglRender(forceNextFrame);
      if (forceNextFrame) {
        scheduleRender(true);
        return;
      }
      if (requiresContinuousRendering()) {
        scheduleRender();
      }
    }
  
    function handleDocumentVisibilityChange() {
      const nextVisible = document.visibilityState !== 'hidden';
      if (nextVisible === isPageVisible) return;
      isPageVisible = nextVisible;
      handleRenderActivityChange(nextVisible);
    }
  
    function handleIntersection(entries) {
      const entry = entries && entries[0];
      if (!entry) return;
      const nextInViewport = entry.isIntersecting && entry.intersectionRatio > 0;
      if (nextInViewport === isInViewport) return;
      isInViewport = nextInViewport;
      handleRenderActivityChange(nextInViewport);
    }
  
    function handleWindowResize() {
      resize();
      scheduleSeparateWebglRender(true);
      scheduleRender(true);
    }
  
    function scheduleRender(force = false) {
      if (force) pendingForceRender = true;
      if (!isActiveForRendering()) {
        if (rafId) {
          cancelAnimationFrame(rafId);
          rafId = null;
        }
        return;
      }
      if (!rafId) rafId = requestAnimationFrame(renderFrame);
    }
  
    function renderSeparateWebgl(now) {
      webglRafId = null;
      if (!isActiveForRendering()) return;
      const uniformValues = getWebglUniformValues();
      syncWebglLayerStyle(uniformValues);
      if (!isSeparateWebglVisible(uniformValues)) return;
      const dpr = window.devicePixelRatio || 1;
      syncOverlayCanvasSize(webglCanvas, webglCtx, renderWidth || viewWidth || 1, renderHeight || viewHeight || 1, dpr);
      syncShaderCanvasSize(renderWidth || viewWidth || 1, renderHeight || viewHeight || 1, dpr);
      if (usesShaderOverlay(uniformValues)) {
        renderShaderOverlayFrame(renderWidth || viewWidth || 1, renderHeight || viewHeight || 1, now, uniformValues);
        webglCtx.clearRect(0, 0, renderWidth || viewWidth || 1, renderHeight || viewHeight || 1);
      } else {
        renderWebglOverlayFrame(
          webglCtx,
          renderWidth || viewWidth || 1,
          renderHeight || viewHeight || 1,
          now,
          uniformValues,
          getWebglMouseState(renderWidth || viewWidth || 1, renderHeight || viewHeight || 1)
        );
        if (webglShaderGl) {
          webglShaderGl.viewport(0, 0, webglShaderCanvas.width || 1, webglShaderCanvas.height || 1);
          webglShaderGl.clearColor(0, 0, 0, 0);
          webglShaderGl.clear(webglShaderGl.COLOR_BUFFER_BIT);
        }
      }
      scheduleSeparateWebglRender();
    }
  
    function scheduleSeparateWebglRender(force = false) {
      const uniformValues = getWebglUniformValues();
      const shouldRun = isActiveForRendering() && isSeparateWebglVisible(uniformValues);
      syncWebglLayerStyle(uniformValues);
      if (!shouldRun) {
        if (webglRafId) {
          cancelAnimationFrame(webglRafId);
          webglRafId = null;
        }
        webglCtx.clearRect(0, 0, renderWidth || viewWidth || 1, renderHeight || viewHeight || 1);
        if (webglShaderGl) {
          webglShaderGl.viewport(0, 0, webglShaderCanvas.width || 1, webglShaderCanvas.height || 1);
          webglShaderGl.clearColor(0, 0, 0, 0);
          webglShaderGl.clear(webglShaderGl.COLOR_BUFFER_BIT);
        }
        return;
      }
      if (force && webglRafId) {
        cancelAnimationFrame(webglRafId);
        webglRafId = null;
      }
      if (!webglRafId) webglRafId = requestAnimationFrame(renderSeparateWebgl);
    }
  
    function toCanvasPoint(event) {
      const rect = canvas.getBoundingClientRect();
      const inside =
        event.clientX >= rect.left &&
        event.clientX <= rect.right &&
        event.clientY >= rect.top &&
        event.clientY <= rect.bottom;
      if (!inside) return null;
      const x = ((event.clientX - rect.left) / Math.max(rect.width, 1)) * renderWidth;
      const y = ((event.clientY - rect.top) / Math.max(rect.height, 1)) * renderHeight;
      return { x: clamp(x, 0, renderWidth), y: clamp(y, 0, renderHeight) };
    }
  
    function handleWindowPointerMove(event) {
      const point = toCanvasPoint(event);
      if (!point) {
        if (pointer.inside) {
          pointer = { ...pointer, inside: false };
          scheduleSeparateWebglRender(true);
          scheduleRender();
        }
        return;
      }
      pointer = { inside: true, x: point.x, y: point.y };
      scheduleSeparateWebglRender(true);
      scheduleRender();
    }
  
    function handleWindowPointerDown(event) {
      const point = toCanvasPoint(event);
      if (!point) return;
      pointer = { inside: true, x: point.x, y: point.y };
      clickBursts = [
        ...clickBursts.slice(-2),
        { x: point.x, y: point.y, startedAt: performance.now(), seed: Math.random() * Math.PI * 2 }
      ];
      scheduleSeparateWebglRender(true);
      scheduleRender();
    }
  
    function handleWindowBlur() {
      if (!pointer.inside) return;
      pointer = { ...pointer, inside: false };
      scheduleSeparateWebglRender(true);
      scheduleRender();
    }
  
    async function loadSource() {
      if (SOURCE.type === 'procedural') {
        return { kind: 'procedural' };
      }
  
      if (SOURCE.type === 'camera') {
        stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false });
        const video = document.createElement('video');
        video.srcObject = stream;
        video.muted = true;
        video.playsInline = true;
        await video.play();
        return video;
      }
  
      if (SOURCE.type === 'video') {
        const video = document.createElement('video');
        video.src = SOURCE.url;
        video.preload = 'auto';
        video.crossOrigin = 'anonymous';
        video.muted = true;
        video.loop = true;
        video.playsInline = true;
        sourceLoopHandler = () => {
          try {
            video.currentTime = 0.001;
            const resumePromise = video.play();
            if (resumePromise && typeof resumePromise.catch === 'function') {
              resumePromise.catch(() => {});
            }
            scheduleRender(true);
          } catch {
            // Ignore loop recovery errors to keep render alive.
          }
        };
        video.addEventListener('ended', sourceLoopHandler);
        await new Promise((resolve, reject) => {
          video.onloadeddata = resolve;
          video.onerror = reject;
        });
        video.currentTime = 0;
        await video.play();
        return video;
      }
  
      const image = new Image();
      image.crossOrigin = 'anonymous';
      image.src = SOURCE.url;
      await new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = reject;
      });
      return image;
    }
  
    function renderFrame(now) {
      rafId = null;
      if (!source) return;
      if (!isActiveForRendering()) {
        syncSourcePlayback(false);
        return;
      }
      const interactionEnabled = Boolean(EXPORT_OPTIONS.enableInteractionEffects);
      if (interactionEnabled) {
        clickBursts = clickBursts.filter((burst) => now - burst.startedAt < CLICK_BURST_DURATION_MS);
      } else if (clickBursts.length) {
        clickBursts = [];
      }
      const forceRender = pendingForceRender;
      pendingForceRender = false;
      const targetFps = getTargetFps(interactionEnabled);
      const minFrameInterval = 1000 / Math.max(1, targetFps);
      if (!forceRender && lastRenderTime > 0 && now - lastRenderTime < minFrameInterval) {
        scheduleRender();
        return;
      }
      lastRenderTime = now;
      const frameStartedAt = performance.now();
      fpsFrameCount += 1;
      if (!fpsWindowStart) fpsWindowStart = now;
      const proceduralMode = source.kind === 'procedural';
  
      const fontSize = clamp(SETTINGS.fontSize || 10, 6, 24);
      const spacing = clamp(SETTINGS.charSpacing ?? 1, 0.7, 2);
      const renderFont = SETTINGS.renderFont || 'Helvetica, Arial, sans-serif';
      const fontDeclaration = fontSize + 'px ' + renderFont;
      ctx.font = fontDeclaration;
      const measuredCharWidth = ctx.measureText('M').width;
      const charWidth = Math.max(fontSize * 0.45, measuredCharWidth || fontSize * 0.62);
      const cellWidth = charWidth * spacing;
      const cellHeight = fontSize * spacing;
      const cols = Math.max(24, Math.floor(viewWidth / cellWidth));
      let contentAspect = viewWidth / Math.max(viewHeight, 1);
      const requestedAspect = parseAspectRatio(SETTINGS.outputAspect);
      let sourceSize = null;
  
      if (!proceduralMode) {
        sourceSize = getSourceSize(source);
        if (!sourceSize.width || !sourceSize.height) {
          scheduleRender();
          return;
        }
        contentAspect = requestedAspect || sourceSize.width / sourceSize.height;
  
        if (SOURCE.type === 'video' && isPlayableVideoSource(source)) {
          const sourceDuration = Number(source.duration);
          if (Number.isFinite(sourceDuration) && sourceDuration > 0) {
            const sourceFps = clamp(Number(SOURCE.fps) || 6, 1, 24);
            const loopThreshold = clamp(Math.max(0.24, 2 / sourceFps), 0.12, 0.75);
            if (sourceDuration - source.currentTime <= loopThreshold) {
              try {
                source.currentTime = 0.001;
                if (source.paused) {
                  source.play().catch(() => {});
                }
                scheduleRender(true);
              } catch {
                // Ignore near-end seek errors and keep rendering.
              }
            }
          }
        }
      }
  
      const cellAspectRatio = cellWidth / Math.max(cellHeight, 1);
      const rows = Math.max(12, Math.round((1 / Math.max(contentAspect, 0.0001)) * cols * cellAspectRatio));
      const outputWidth = Math.max(1, Math.floor(cols * cellWidth));
      const outputHeight = Math.max(1, Math.ceil(rows * cellHeight));
      const dpr = window.devicePixelRatio || 1;
      const webglUniformValues = getWebglUniformValues();
      if (
        outputWidth !== renderWidth ||
        outputHeight !== renderHeight ||
        canvas.width !== Math.max(1, Math.round(outputWidth * dpr)) ||
        canvas.height !== Math.max(1, Math.round(outputHeight * dpr))
      ) {
        renderWidth = outputWidth;
        renderHeight = outputHeight;
        canvas.width = Math.max(1, Math.round(renderWidth * dpr));
        canvas.height = Math.max(1, Math.round(renderHeight * dpr));
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.font = fontDeclaration;
      }
      syncWebglLayerStyle(webglUniformValues);
      syncOverlayCanvasSize(webglCanvas, webglCtx, outputWidth, outputHeight, dpr);
      syncShaderCanvasSize(outputWidth, outputHeight, dpr);
      if (!isSeparateWebglVisible(webglUniformValues)) {
        webglCtx.clearRect(0, 0, outputWidth, outputHeight);
        if (webglShaderGl) {
          webglShaderGl.viewport(0, 0, webglShaderCanvas.width || 1, webglShaderCanvas.height || 1);
          webglShaderGl.clearColor(0, 0, 0, 0);
          webglShaderGl.clear(webglShaderGl.COLOR_BUFFER_BIT);
        }
      }
      lastCharCount = cols * rows;
  
      const charset = selectCharset();
      const timeSeconds = now * 0.001;
      const grayscale = new Float32Array(cols * rows);
      let data;
  
      sampleCanvas.width = cols;
      sampleCanvas.height = rows;
  
      if (proceduralMode) {
        const proceduralPreset = SOURCE.proceduralPreset || 'flow';
        const proceduralPixels = new Uint8ClampedArray(cols * rows * 4);
        data = proceduralPixels;
  
        for (let y = 0; y < rows; y += 1) {
          for (let x = 0; x < cols; x += 1) {
            const idx = y * cols + x;
            const offset = idx * 4;
            const field = proceduralField(x, y, cols, rows, timeSeconds);
            const pulse = 0.5 + 0.5 * Math.sin(timeSeconds * 1.8 + x * 0.06 - y * 0.04);
            const mixed = clamp(field * 0.78 + pulse * 0.22, 0, 1);
            const baseGray = Math.floor(mixed * 255);
  
            let r = baseGray;
            let g = baseGray;
            let b = baseGray;
  
            if (proceduralPreset === 'plasma') {
              r = clamp(Math.floor(baseGray * 0.72 + 92 * (0.5 + 0.5 * Math.sin(timeSeconds * 1.1 + y * 0.09))), 0, 255);
              g = clamp(Math.floor(baseGray * 0.48 + 74 * (0.5 + 0.5 * Math.cos(timeSeconds * 1.6 + x * 0.07))), 0, 255);
              b = clamp(Math.floor(baseGray * 0.84 + 102 * (0.5 + 0.5 * Math.sin(timeSeconds * 1.35 + (x + y) * 0.05))), 0, 255);
            } else if (proceduralPreset === 'mono') {
              const mono = clamp(Math.floor(baseGray * 1.08), 0, 255);
              r = mono;
              g = mono;
              b = mono;
            } else {
              r = clamp(Math.floor(baseGray * 0.64 + 86 * (0.5 + 0.5 * Math.sin(timeSeconds * 1.2 + x * 0.11))), 0, 255);
              g = clamp(Math.floor(baseGray * 0.82 + 64 * (0.5 + 0.5 * Math.sin(timeSeconds * 1.45 + y * 0.08))), 0, 255);
              b = clamp(Math.floor(baseGray * 0.58 + 74 * (0.5 + 0.5 * Math.cos(timeSeconds * 1.05 + (x - y) * 0.07))), 0, 255);
            }
  
            proceduralPixels[offset] = r;
            proceduralPixels[offset + 1] = g;
            proceduralPixels[offset + 2] = b;
            proceduralPixels[offset + 3] = 255;
  
            const toned = applyTone(baseGray);
            grayscale[idx] = applyOverlayFx(toned, x, y, cols, rows, timeSeconds);
          }
        }
      } else {
        const sampleTargetAspect = (cols * cellWidth) / Math.max(rows * cellHeight, 1);
        const { cropX, cropY, cropWidth, cropHeight } = getCoverCropRect(
          sourceSize.width,
          sourceSize.height,
          sampleTargetAspect
        );
        sampleCtx.drawImage(source, cropX, cropY, cropWidth, cropHeight, 0, 0, cols, rows);
        const pixels = sampleCtx.getImageData(0, 0, cols, rows);
        data = pixels.data;
  
        for (let y = 0; y < rows; y += 1) {
          for (let x = 0; x < cols; x += 1) {
            const idx = y * cols + x;
            const offset = idx * 4;
            const r = data[offset];
            const g = data[offset + 1];
            const b = data[offset + 2];
            const baseGray = 0.299 * r + 0.587 * g + 0.114 * b;
            const toned = applyTone(baseGray);
            grayscale[idx] = applyOverlayFx(toned, x, y, cols, rows, timeSeconds);
          }
        }
      }
  
      if (isWebglAsciiFxEnabled()) {
        blendWebglIntoData(data, cols, rows, now, webglUniformValues);
        for (let y = 0; y < rows; y += 1) {
          for (let x = 0; x < cols; x += 1) {
            const idx = y * cols + x;
            const offset = idx * 4;
            const r = data[offset];
            const g = data[offset + 1];
            const b = data[offset + 2];
            const baseGray = 0.299 * r + 0.587 * g + 0.114 * b;
            const toned = applyTone(baseGray);
            grayscale[idx] = applyOverlayFx(toned, x, y, cols, rows, timeSeconds);
          }
        }
      }
  
      if (SETTINGS.ditherType === 'bayer') {
        for (let y = 0; y < rows; y += 1) {
          for (let x = 0; x < cols; x += 1) {
            const idx = y * cols + x;
            const threshold = bayerThreshold(x, y);
            const offset = (threshold - 0.5) * 255 * SETTINGS.ditherStrength;
            grayscale[idx] = clamp(grayscale[idx] + offset, 0, 255);
          }
        }
      }
  
      if (SETTINGS.ditherType === 'floyd-steinberg' || SETTINGS.ditherType === 'atkinson') {
        const work = new Float32Array(grayscale);
        for (let y = 0; y < rows; y += 1) {
          for (let x = 0; x < cols; x += 1) {
            const idx = y * cols + x;
            const oldValue = work[idx];
            const step = 255 / Math.max(2, charset.length - 1);
            const newValue = Math.round(oldValue / step) * step;
            const error = (oldValue - newValue) * SETTINGS.ditherStrength;
            work[idx] = clamp(newValue, 0, 255);
  
            if (SETTINGS.ditherType === 'floyd-steinberg') {
              if (x + 1 < cols) work[idx + 1] += (error * 7) / 16;
              if (x - 1 >= 0 && y + 1 < rows) work[idx + cols - 1] += (error * 3) / 16;
              if (y + 1 < rows) work[idx + cols] += (error * 5) / 16;
              if (x + 1 < cols && y + 1 < rows) work[idx + cols + 1] += error / 16;
            } else {
              if (x + 1 < cols) work[idx + 1] += error / 8;
              if (x + 2 < cols) work[idx + 2] += error / 8;
              if (x - 1 >= 0 && y + 1 < rows) work[idx + cols - 1] += error / 8;
              if (y + 1 < rows) work[idx + cols] += error / 8;
              if (x + 1 < cols && y + 1 < rows) work[idx + cols + 1] += error / 8;
              if (y + 2 < rows) work[idx + cols * 2] += error / 8;
            }
          }
        }
        for (let i = 0; i < grayscale.length; i += 1) {
          grayscale[i] = clamp(work[i], 0, 255);
        }
      }
  
      ctx.clearRect(0, 0, renderWidth, renderHeight);
      ctx.font = fontDeclaration;
      ctx.textBaseline = 'top';
      const hoverAttractStrength = clamp(SETTINGS.hoverStrength ?? 24, 4, 64);
      const hoverAreaSize = clamp(SETTINGS.mouseAreaSize ?? HOVER_ATTRACT_RADIUS, 40, 640);
      const hoverSpread = clamp(SETTINGS.mouseSpread ?? 1, 0.25, 3);
      const hoverDirection = SETTINGS.mouseInteractionMode === 'push' ? -1 : 1;
      const bgDitherStrength = clamp(Number(SETTINGS.bgDither ?? 0) || 0, 0, 3);
      const inverseDitherStrength = clamp(Number(SETTINGS.inverseDither ?? 0) || 0, 0, 3);
      const foregroundOpacity = clamp(Number(SETTINGS.opacity ?? 1) || 0, 0, 1);
      const vignetteStrength = clamp(Number(SETTINGS.vignette ?? 0) || 0, 0, 1);
      const borderGlowStrength = clamp(Number(SETTINGS.borderGlow ?? 0) || 0, 0, 1);
      const invertedBackground = invertCssColor(SETTINGS.backgroundColor || '#000000');
      const hasPointerAttraction = interactionEnabled && pointer.inside;
      const hasBurst = interactionEnabled && clickBursts.length > 0;
      const matrixMode = SETTINGS.overlayPreset === 'matrix';
      const matrixStrength = clamp(SETTINGS.overlayStrength ?? 0.45, 0, 1);
      let matrixBoost = null;
  
      if (matrixMode) {
        const matrixScale = clamp(SETTINGS.matrixScale ?? 15, 6, 48);
        const matrixSpeed = clamp(SETTINGS.matrixSpeed ?? 0.1, 0.1, 4);
        const laneScale = clamp(matrixScale / 12, 0.6, 4);
        const projection = getDirectionProjection(SETTINGS.matrixDirection || 'down');
        const primaryCount = Math.max(cols, rows);
        const secondaryCount = Math.max(cols, rows);
        const laneCount = Math.max(6, Math.ceil(secondaryCount / laneScale));
        if (
          matrixRainState.laneCount !== laneCount ||
          matrixRainState.primaryCount !== primaryCount ||
          matrixRainState.speeds.length !== laneCount
        ) {
          matrixRainState = {
            laneCount,
            primaryCount,
            speeds: Array.from({ length: laneCount }, () => 0.55 + Math.random() * 1.85),
            phases: Array.from({ length: laneCount }, () => Math.random() * (primaryCount + 36)),
            lengths: Array.from({ length: laneCount }, () =>
              Math.max(7, Math.round(primaryCount * (0.2 + Math.random() * 0.38)))
            ),
          };
        }
  
        matrixBoost = new Float32Array(cols * rows);
        const laneHeads = new Float32Array(laneCount);
        const laneLengths = new Float32Array(laneCount);
        for (let lane = 0; lane < laneCount; lane += 1) {
          const trailLength = matrixRainState.lengths[lane];
          const cycle = primaryCount + trailLength + 12;
          const head =
            ((timeSeconds * matrixRainState.speeds[lane] * matrixSpeed * primaryCount +
              matrixRainState.phases[lane]) %
              cycle) -
            trailLength;
          laneHeads[lane] = head;
          laneLengths[lane] = trailLength;
  
          if (Math.random() < 0.0032) {
            matrixRainState.speeds[lane] = 0.55 + Math.random() * 1.85;
            matrixRainState.phases[lane] = Math.random() * (primaryCount + 36);
            matrixRainState.lengths[lane] = Math.max(7, Math.round(primaryCount * (0.2 + Math.random() * 0.38)));
          }
        }
  
        for (let y = 0; y < rows; y += 1) {
          for (let x = 0; x < cols; x += 1) {
            const idx = y * cols + x;
            const { primaryNorm, secondaryNorm } = projectDirection(x, y, cols, rows, projection);
            const lane = clamp(Math.floor(secondaryNorm * laneCount), 0, laneCount - 1);
            const primary = primaryNorm * (primaryCount - 1);
            const distance = laneHeads[lane] - primary;
            if (distance < 0 || distance > laneLengths[lane]) continue;
            const falloff = 1 - distance / (laneLengths[lane] + 1);
            matrixBoost[idx] = falloff * (44 + matrixStrength * 148 + falloff * (62 + matrixStrength * 30));
          }
        }
      }
  
      ctx.globalAlpha = foregroundOpacity;
      for (let y = 0; y < rows; y += 1) {
        for (let x = 0; x < cols; x += 1) {
          const idx = y * cols + x;
          const pixelOffset = idx * 4;
          const gray = Math.round(grayscale[idx]);
          const inverseCoverage = shouldApplyInverseDither(gray, x, y, inverseDitherStrength, timeSeconds);
          const invertCell = inverseCoverage > 0.12;
          const mappedGray = clamp(Math.round(gray + (255 - gray * 2) * inverseCoverage), 0, 255);
          const r = data[pixelOffset];
          const g = data[pixelOffset + 1];
          const b = data[pixelOffset + 2];
          const nx = cols > 1 ? (x / (cols - 1)) * 2 - 1 : 0;
          const ny = rows > 1 ? (y / (rows - 1)) * 2 - 1 : 0;
          const radial = Math.sqrt(nx * nx + ny * ny) / Math.SQRT2;
          const vignetteCore = Math.pow(clamp(1 - radial, 0, 1), 1 + vignetteStrength * 2);
          const vignetteFactor = 1 - vignetteStrength + vignetteStrength * vignetteCore;
          const cellAlpha = foregroundOpacity * vignetteFactor;
          if (cellAlpha <= 0.002) continue;
          ctx.globalAlpha = cellAlpha;
          const baseX = x * cellWidth;
          const baseY = y * cellHeight;
          if (bgDitherStrength > 0) {
            const tone = gray / 255;
            const threshold = bayerThreshold(x, y);
            const drift = (Math.sin((x + 1) * 7.31 + (y + 1) * 3.17 + timeSeconds * 0.75) + 1) * 0.5;
            const pattern = threshold * 0.72 + drift * 0.28;
            const coverage = clamp(tone * (0.92 + bgDitherStrength * 0.9) - pattern + 0.34, 0, 1);
            if (coverage > 0.04) {
              const dotFactor = clamp(0.18 + coverage * (0.85 + bgDitherStrength * 0.5), 0.12, 1);
              const dotSize = Math.max(0.45, Math.min(cellWidth, cellHeight) * dotFactor);
              const insetX = (cellWidth - dotSize) * 0.5;
              const insetY = (cellHeight - dotSize) * 0.5;
              const tint = getBackgroundDitherColor(r, g, b, gray);
              const alpha = clamp(coverage * (0.05 + bgDitherStrength * 0.34), 0, 1);
              ctx.fillStyle = applyOutputPolarity(
                'rgba(' + tint.r + ', ' + tint.g + ', ' + tint.b + ', ' + alpha.toFixed(3) + ')'
              );
              ctx.fillRect(baseX + insetX, baseY + insetY, dotSize, dotSize);
            }
          }
  
          if (inverseCoverage > 0.01) {
            const invAlpha = clamp(inverseCoverage * (0.08 + inverseDitherStrength * 0.34), 0, 1);
            if (invAlpha > 0.005) {
              const previousAlpha = ctx.globalAlpha;
              ctx.globalAlpha = previousAlpha * invAlpha;
              ctx.fillStyle = invertedBackground;
              ctx.fillRect(baseX, baseY, cellWidth, cellHeight);
              ctx.globalAlpha = previousAlpha;
            }
          }
  
          const baseColor = colorFromMode(r, g, b, mappedGray, x, y, cols, rows);
          ctx.fillStyle = applyOutputPolarity(baseColor, invertCell);
          let drawX = baseX;
          let drawY = baseY;
          let centerX = drawX + cellWidth * 0.5;
          let centerY = drawY + cellHeight * 0.5;
  
          if (hasPointerAttraction || hasBurst) {
            let offsetX = 0;
            let offsetY = 0;
  
            if (hasPointerAttraction) {
              const dx = pointer.x - centerX;
              const dy = pointer.y - centerY;
              const distance = Math.hypot(dx, dy);
              if (distance > 0.0001 && distance < hoverAreaSize) {
                const falloff = 1 - distance / hoverAreaSize;
                const spreadFactor = Math.pow(falloff, 1 / hoverSpread);
                const pull = spreadFactor * spreadFactor * hoverAttractStrength * hoverDirection;
                offsetX += (dx / distance) * pull;
                offsetY += (dy / distance) * pull;
              }
            }
  
            if (hasBurst) {
              for (let burstIndex = 0; burstIndex < clickBursts.length; burstIndex += 1) {
                const burst = clickBursts[burstIndex];
                const age = now - burst.startedAt;
                if (age >= CLICK_BURST_DURATION_MS) continue;
                const progress = clamp(age / CLICK_BURST_DURATION_MS, 0, 1);
                const dx = centerX - burst.x;
                const dy = centerY - burst.y;
                const distance = Math.hypot(dx, dy);
                if (distance >= CLICK_BURST_RADIUS) continue;
                const falloff = 1 - distance / CLICK_BURST_RADIUS;
                const impulse =
                  CLICK_BURST_STRENGTH *
                  falloff *
                  (1 - progress * 0.55) *
                  (1.25 + Math.sin(progress * Math.PI) * 0.45);
                let dirX = 1;
                let dirY = 0;
                if (distance > 0.0001) {
                  dirX = dx / distance;
                  dirY = dy / distance;
                } else {
                  const angle = (idx + burst.seed) * 0.61803398875;
                  dirX = Math.cos(angle);
                  dirY = Math.sin(angle);
                }
                offsetX += dirX * impulse;
                offsetY += dirY * impulse;
              }
            }
  
            drawX += offsetX;
            drawY += offsetY;
            centerX += offsetX;
            centerY += offsetY;
          }
  
          if (matrixMode) {
            const boost = matrixBoost ? matrixBoost[idx] : 0;
            const ambient = 6 + matrixStrength * 14;
            const baseContrast = clamp((mappedGray - 128) * (1.2 + matrixStrength * 0.55) + 128, 0, 255);
            const composedGray = clamp(Math.round(baseContrast * 0.38 + boost * 0.78 + ambient), 0, 255);
            if (composedGray < 20) continue;
  
            const glyphClock = timeSeconds * (10 + clamp(SETTINGS.matrixSpeed ?? 0.1, 0.1, 4) * 16);
            const drift =
              Math.sin((x + 1) * 2.17 + glyphClock * 1.7) +
              Math.cos((y + 1) * 1.93 - glyphClock * 1.1);
            const scramble = Math.sin((x + 1) * 91.13 + (y + 1) * 37.77 + glyphClock * 5.3 + boost * 0.06);
            const noise = drift * 0.28 + scramble * 0.72;
            let mapped = Math.floor(clamp((noise + 2) / 4, 0, 1) * (MATRIX_CHARS.length - 1));
            const jumpToken = Math.sin((Math.floor(glyphClock * 2.6) + x * 13 + y * 7) * 12.9898);
            if (jumpToken > 0.93) {
              mapped = 1 + ((Math.floor(glyphClock * 11) + x * 3 + y * 5) % (MATRIX_CHARS.length - 1));
            }
            const char = MATRIX_CHARS[clamp(mapped, 1, MATRIX_CHARS.length - 1)];
            if (char === ' ') continue;
  
            const isHead = boost > 182;
            const glowAlpha = clamp(0.08 + composedGray / 620 + (isHead ? 0.12 : 0), 0, 0.56);
            const glowGreen = clamp(Math.floor(72 + composedGray * 0.58), 0, 255);
            const glowRed = clamp(Math.floor(glowGreen * 0.24), 0, 160);
            const glowBlue = clamp(Math.floor(glowGreen * 0.34), 0, 180);
            const glowColor = 'rgb(' + glowRed + ', ' + glowGreen + ', ' + glowBlue + ')';
            const glowShadowColor = 'rgba(' + glowRed + ', ' + glowGreen + ', ' + glowBlue + ', ' + glowAlpha + ')';
            ctx.fillStyle = applyOutputPolarity(glowColor, invertCell);
            ctx.shadowColor = applyOutputPolarity(glowShadowColor, invertCell);
            ctx.shadowBlur = isHead ? Math.max(3, fontSize * 0.75) : Math.max(1.5, fontSize * 0.32);
            ctx.fillText(char, drawX, drawY);
            ctx.shadowBlur = 0;
            continue;
          }
  
          if (SETTINGS.style === 'halftone') {
            const halftoneShape = String(SETTINGS.halftoneShape || 'circle');
            const halftoneSize = clamp(Number(SETTINGS.halftoneSize ?? 1) || 1, 0.4, 2.2);
            const halftoneRotation = clamp(Number(SETTINGS.halftoneRotation ?? 0) || 0, -180, 180);
            const normalized = mappedGray / 255;
            const screen =
              (Math.sin((x * 0.82 + y * 0.33) * 1.55) + Math.cos((x * 0.27 - y * 0.94) * 1.25) + 2) * 0.25;
            const dotLevel = clamp(Math.pow(normalized, 0.92) * 0.82 + screen * 0.18, 0, 1);
            const maxRadius = Math.max(0.1, Math.min(cellWidth, cellHeight) * 0.5);
            const radius = maxRadius * dotLevel * halftoneSize;
            if (radius < 0.35) continue;
  
            drawHalftoneShape(ctx, halftoneShape, centerX, centerY, radius, halftoneRotation);
            continue;
          }
  
          if (SETTINGS.style === 'line') {
            const normalized = mappedGray / 255;
            const lengthScale = clamp(SETTINGS.lineLength ?? 1, 0.1, 2.5);
            const widthScale = clamp(SETTINGS.lineWidth ?? 1, 0.2, 2.5);
            const thicknessSetting = clamp(SETTINGS.lineThickness ?? 1.6, 0.2, 8);
            const rotationDeg = SETTINGS.lineRotation ?? 0;
            const screen =
              (Math.sin((x * 0.79 + y * 0.41) * 1.37) + Math.cos((x * 0.33 - y * 0.93) * 1.09) + 2) * 0.25;
            const angle = (rotationDeg * Math.PI) / 180 + (screen - 0.5) * 0.55;
            const spanBase = Math.max(0.8, Math.min(cellWidth, cellHeight) * widthScale);
            const span = spanBase * clamp(normalized * lengthScale, 0.05, 1.5);
            if (span < 0.6) continue;
            const half = span * 0.5;
            const x0 = centerX - Math.cos(angle) * half;
            const y0 = centerY - Math.sin(angle) * half;
            const x1 = centerX + Math.cos(angle) * half;
            const y1 = centerY + Math.sin(angle) * half;
            const thicknessPx = clamp(thicknessSetting, 0.2, Math.max(0.2, Math.min(cellWidth, cellHeight) * 1.4));
            const lineColor = colorFromMode(r, g, b, mappedGray, x, y, cols, rows);
            ctx.strokeStyle = applyOutputPolarity(lineColor, invertCell);
            ctx.lineWidth = thicknessPx;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(x0, y0);
            ctx.lineTo(x1, y1);
            ctx.stroke();
            continue;
          }
  
          const edgeContrast =
            SETTINGS.style === 'dotcross' || SETTINGS.style === 'braille' || SETTINGS.style === 'particles'
              ? getLocalEdgeContrast(grayscale, x, y, cols, rows)
              : 0;
          const brailleVariant = String(SETTINGS.brailleVariant || 'standard');
          const brailleBoost =
            SETTINGS.style === 'braille'
              ? 8 + edgeContrast * 40 + (brailleVariant === 'dense' ? 10 : brailleVariant === 'sparse' ? -4 : 4)
              : 0;
          const particleDensity = clamp(SETTINGS.particleDensity ?? 0.5, 0.05, 1);
          const particleBoost =
            SETTINGS.style === 'particles' ? edgeContrast * 44 + (particleDensity - 0.5) * 12 : 0;
          const glyphGray =
            SETTINGS.style === 'braille'
              ? clamp(mappedGray + brailleBoost, 0, 255)
              : SETTINGS.style === 'particles'
                ? clamp(mappedGray + particleBoost, 0, 255)
                : mappedGray;
          const char = charFromGray(glyphGray, charset, x, y, cols, rows, edgeContrast);
          if (char === ' ') continue;
          const glyphColor = colorFromMode(r, g, b, glyphGray, x, y, cols, rows, edgeContrast);
          ctx.fillStyle = applyOutputPolarity(glyphColor, invertCell);
          ctx.fillText(char, drawX, drawY);
        }
      }
  
      if (borderGlowStrength > 0.001) {
        drawBorderGlowOverlay(ctx, renderWidth, renderHeight, borderGlowStrength);
      }
      ctx.globalAlpha = 1;
      lastFrameDurationMs = Math.max(0, performance.now() - frameStartedAt);
      const fpsElapsed = now - fpsWindowStart;
      if (fpsElapsed >= 500) {
        const nextFps = Math.round((fpsFrameCount * 1000) / fpsElapsed);
        reportFps(Number.isFinite(nextFps) ? nextFps : 0, {
          chars: lastCharCount,
          frameMs: lastFrameDurationMs,
        });
        fpsFrameCount = 0;
        fpsWindowStart = now;
      }
  
      if (requiresContinuousRendering(interactionEnabled)) {
        scheduleRender();
      }
    }
  
    async function start() {
      resize();
      document.addEventListener('visibilitychange', handleDocumentVisibilityChange);
      window.addEventListener('resize', handleWindowResize);
      if (typeof IntersectionObserver === 'function') {
        const visibilityThreshold = clamp(Number(EXPORT_OPTIONS.visibilityThreshold ?? 0.01) || 0.01, 0, 1);
        intersectionObserver = new IntersectionObserver(handleIntersection, {
          threshold: [0, visibilityThreshold, 0.25],
        });
        intersectionObserver.observe(mount);
      }
      if (typeof ResizeObserver === 'function') {
        resizeObserver = new ResizeObserver(() => {
          resize();
          scheduleSeparateWebglRender(true);
          scheduleRender(true);
        });
        resizeObserver.observe(mount);
      }
      if (EXPORT_OPTIONS.enableInteractionEffects) {
        window.addEventListener('pointermove', handleWindowPointerMove, { passive: true });
        window.addEventListener('pointerdown', handleWindowPointerDown, { passive: true });
        window.addEventListener('blur', handleWindowBlur);
      }
      source = await loadSource();
      handleRenderActivityChange(true);
    }
  
    start().catch((error) => {
      reportFps(0);
      drawError('Export source failed: ' + (error && error.message ? error.message : 'Unknown error'));
    });
  
    window.__asciiDitherExportDestroy = function() {
      reportFps(0);
      if (rafId) cancelAnimationFrame(rafId);
      if (webglRafId) cancelAnimationFrame(webglRafId);
      if (stream) stream.getTracks().forEach((track) => track.stop());
      document.removeEventListener('visibilitychange', handleDocumentVisibilityChange);
      window.removeEventListener('resize', handleWindowResize);
      if (intersectionObserver) intersectionObserver.disconnect();
      if (resizeObserver) resizeObserver.disconnect();
      if (sourceLoopHandler && source && typeof source.removeEventListener === 'function') {
        source.removeEventListener('ended', sourceLoopHandler);
        sourceLoopHandler = null;
      }
      window.removeEventListener('pointermove', handleWindowPointerMove);
      window.removeEventListener('pointerdown', handleWindowPointerDown);
      window.removeEventListener('blur', handleWindowBlur);
      disposeWebglShaderResources();
      mount.replaceChildren();
      delete mount.__asciiDitherDestroy;
      if (IS_TEMPLATE_PREVIEW_RUNTIME) {
        const runtimeEntry = runtimeScope[TEMPLATE_PREVIEW_RUNTIME_KEY];
        if (runtimeEntry && runtimeEntry.id === previewRuntimeId) {
          delete runtimeScope[TEMPLATE_PREVIEW_RUNTIME_KEY];
        }
      }
    };
    mount.__asciiDitherDestroy = window.__asciiDitherExportDestroy;
    if (IS_TEMPLATE_PREVIEW_RUNTIME) {
      const runtimeEntry = runtimeScope[TEMPLATE_PREVIEW_RUNTIME_KEY];
      if (runtimeEntry && runtimeEntry.id === previewRuntimeId) {
        runtimeEntry.destroy = window.__asciiDitherExportDestroy;
      }
    }
  })();
  