import json
from typing import Optional
from pages.line_mark_stage_js import get_stage_hover_swap_script, get_stage_image_zoom_script


def get_canvas_enhancement_script(
    source_image_url: str = "",
    zoom_factor: int = 4,
    points: Optional[list[tuple[float, float]]] = None,
    move_radius_px: float = 10.0,
) -> str:
    script = """
    <script>
    (function applyCanvasEnhancements() {
      const sourceImageUrl = __SOURCE_IMAGE_URL__;
      const zoomFactor = __ZOOM_FACTOR__;
      const pointList = __POINTS__;
      const moveRadiusPx = __MOVE_RADIUS_PX__;
      const crosshairCursor = "crosshair";
      window.parent.__lineMarkZoomMode = "canvas";
      const styleId = "line-mark-crosshair-style";
      const css = `
        html, body { cursor: default; }
        canvas, .upper-canvas, .lower-canvas, .canvas-container { cursor: none !important; touch-action: none; }
        [class*="CanvasToolbar_"] { display: none !important; }
        button[aria-label*="undo" i], button[aria-label*="redo" i], button[aria-label*="delete" i], button[title*="Undo"], button[title*="Redo"], button[title*="Delete"] { display: none !important; }
        button, [role="button"] { color: #f3f4f6 !important; opacity: 1 !important; }
        svg, svg * { stroke: #f3f4f6 !important; fill: #f3f4f6 !important; opacity: 1 !important; }
      `;
      const frames = window.parent.document.querySelectorAll("iframe");
      frames.forEach((frame) => {
        try {
          if (window.parent.__lineMarkZoomMode !== "canvas") return;
          // Disable stage-image zoom while point-canvas zoom is active.
          const parentPanel = window.parent.document.getElementById("line-mark-side-zoom");
          if (parentPanel) parentPanel.remove();
          const stageMove = window.parent.__lineMarkStageMove;
          if (stageMove) {
            window.parent.document.removeEventListener("mousemove", stageMove, true);
            window.parent.__lineMarkStageMove = null;
          }

          const doc = frame.contentDocument || frame.contentWindow.document;
          if (!doc) return;
          if (!doc.getElementById(styleId)) {
            const style = doc.createElement("style");
            style.id = styleId;
            style.textContent = css;
            doc.head.appendChild(style);
          }

          const upperCanvas = doc.querySelector("canvas.upper-canvas");
          if (!upperCanvas) return;
          const lowerCanvas = doc.querySelector("canvas.lower-canvas");
          // Streamlit Cloud often fails to load /media/ URLs inside the drawable-canvas iframe.
          // The zoom lens already uses this JPEG data URL; paint the same image on the background layer.
          const resolveBackgroundCanvas = () => {
            const byId = doc.getElementById("backgroundimage-canvas");
            if (byId && byId.width && byId.height) return byId;
            const drawableContainer = upperCanvas.closest(".canvas-container");
            const candidates = Array.from(doc.querySelectorAll("canvas")).filter((node) => {
              if (node === upperCanvas || node === lowerCanvas) return false;
              if (drawableContainer && drawableContainer.contains(node)) return false;
              return node.width > 0 && node.height > 0;
            });
            return candidates.length ? candidates[0] : null;
          };
          const paintDrawableBackground = (loadedImage) => {
            if (!sourceImageUrl) return;
            const backgroundCanvas = resolveBackgroundCanvas();
            if (!backgroundCanvas) return;
            const backgroundContext = backgroundCanvas.getContext("2d");
            if (!backgroundContext) return;
            const drawLoadedImage = (imageNode) => {
              try {
                backgroundContext.clearRect(0, 0, backgroundCanvas.width, backgroundCanvas.height);
                backgroundContext.drawImage(
                  imageNode,
                  0,
                  0,
                  backgroundCanvas.width,
                  backgroundCanvas.height,
                );
              } catch (error) {}
            };
            if (loadedImage && loadedImage.complete && loadedImage.naturalWidth > 0) {
              drawLoadedImage(loadedImage);
              return;
            }
            const backgroundImage = new Image();
            backgroundImage.onload = () => drawLoadedImage(backgroundImage);
            backgroundImage.src = sourceImageUrl;
          };
          paintDrawableBackground(null);
          [80, 220, 420, 700, 1200].forEach((delayMs) => {
            window.setTimeout(() => paintDrawableBackground(null), delayMs);
          });
          const applyCursorStyle = (cursorValue) => {
            let resolvedCursor = "none";
            if (cursorValue === "default") resolvedCursor = "default";
            if (cursorValue === "move") resolvedCursor = "move";
            const upperParent = upperCanvas ? upperCanvas.parentElement : null;
            const lowerParent = lowerCanvas ? lowerCanvas.parentElement : null;
            const nodes = [upperCanvas, lowerCanvas, upperParent, lowerParent].filter(Boolean);
            nodes.forEach((node) => {
              try {
                node.style.setProperty("cursor", resolvedCursor, "important");
              } catch (error) {}
            });
          };
          applyCursorStyle("crosshair");
          const hideToolbarControls = () => {
            const toolbarSelectors = [
              "[class*='CanvasToolbar_']",
              "div.canvas-toolbar",
              "div[class^='canvas-toolbar_']",
              "div[class*=' canvas-toolbar_']",
            ].join(", ");
            const toolbarNodes = Array.from(doc.querySelectorAll(toolbarSelectors));
            toolbarNodes.forEach((node) => {
              if (!node || !node.style) return;
              if (node.closest(".canvas-container")) {
                return;
              }
              node.style.setProperty("display", "none", "important");
              node.style.setProperty("visibility", "hidden", "important");
              node.style.setProperty("pointer-events", "none", "important");
              node.style.setProperty("opacity", "0", "important");
            });
          };
          hideToolbarControls();
          [80, 220, 420, 700].forEach((delayMs) => {
            window.setTimeout(hideToolbarControls, delayMs);
          });
          if (window.__lineMarkToolbarObserver) {
            try {
              window.__lineMarkToolbarObserver.disconnect();
            } catch (error) {}
          }
          window.__lineMarkToolbarObserver = new MutationObserver(() => {
            hideToolbarControls();
            paintDrawableBackground(null);
          });
          window.__lineMarkToolbarObserver.observe(doc.body, { childList: true, subtree: true });

          let lens = doc.getElementById("line-mark-lens");
          if (!lens) {
            lens = doc.createElement("canvas");
            lens.id = "line-mark-lens";
            lens.width = 60;
            lens.height = 60;
            lens.style.position = "fixed";
            lens.style.pointerEvents = "none";
            lens.style.zIndex = "2147483647";
            lens.style.border = "1px solid #00ffff";
            lens.style.borderRadius = "50%";
            lens.style.boxShadow = "0 0 0 1px rgba(0,0,0,0.7)";
            lens.style.display = "none";
            doc.body.appendChild(lens);
          }
          let cursorOverlay = doc.getElementById("line-mark-cursor-overlay");
          let cursorOverlayHorizontal = null;
          let cursorOverlayVertical = null;
          let cursorOverlayMoveArrows = [];
          if (!cursorOverlay) {
            cursorOverlay = doc.createElement("div");
            cursorOverlay.id = "line-mark-cursor-overlay";
            cursorOverlay.style.position = "fixed";
            cursorOverlay.style.pointerEvents = "none";
            cursorOverlay.style.zIndex = "2147483647";
            cursorOverlay.style.width = "24px";
            cursorOverlay.style.height = "24px";
            cursorOverlay.style.display = "none";
            cursorOverlay.style.opacity = "1";
            cursorOverlay.style.transform = "scale(1)";
            cursorOverlay.style.transformOrigin = "12px 12px";
            cursorOverlayHorizontal = doc.createElement("div");
            cursorOverlayHorizontal.style.position = "absolute";
            cursorOverlayHorizontal.style.left = "4px";
            cursorOverlayHorizontal.style.top = "12px";
            cursorOverlayHorizontal.style.width = "16px";
            cursorOverlayHorizontal.style.height = "1px";
            cursorOverlayHorizontal.style.background = "rgb(0,255,255)";
            cursorOverlayHorizontal.className = "line-mark-cursor-crosshair-h";
            cursorOverlayVertical = doc.createElement("div");
            cursorOverlayVertical.style.position = "absolute";
            cursorOverlayVertical.style.left = "12px";
            cursorOverlayVertical.style.top = "4px";
            cursorOverlayVertical.style.width = "1px";
            cursorOverlayVertical.style.height = "16px";
            cursorOverlayVertical.style.background = "rgb(0,255,255)";
            cursorOverlayVertical.className = "line-mark-cursor-crosshair-v";
            const makeMoveArrow = (leftPx, topPx, rotationDeg) => {
              const arrow = doc.createElement("div");
              arrow.className = "line-mark-cursor-move-arrow";
              arrow.style.position = "absolute";
              arrow.style.left = `${leftPx}px`;
              arrow.style.top = `${topPx}px`;
              arrow.style.width = "0";
              arrow.style.height = "0";
              arrow.style.borderLeft = "3px solid transparent";
              arrow.style.borderRight = "3px solid transparent";
              arrow.style.borderTop = "5px solid rgb(0,255,255)";
              arrow.style.transform = `rotate(${rotationDeg}deg)`;
              arrow.style.transformOrigin = "50% 50%";
              arrow.style.display = "none";
              return arrow;
            };
            cursorOverlayMoveArrows = [
              makeMoveArrow(9, 1, 0),
              makeMoveArrow(18, 9, 90),
              makeMoveArrow(9, 18, 180),
              makeMoveArrow(1, 9, 270),
            ];
            cursorOverlay.appendChild(cursorOverlayHorizontal);
            cursorOverlay.appendChild(cursorOverlayVertical);
            cursorOverlayMoveArrows.forEach((arrow) => cursorOverlay.appendChild(arrow));
            doc.body.appendChild(cursorOverlay);
          } else {
            cursorOverlayHorizontal = cursorOverlay.querySelector(".line-mark-cursor-crosshair-h");
            cursorOverlayVertical = cursorOverlay.querySelector(".line-mark-cursor-crosshair-v");
            cursorOverlayMoveArrows = Array.from(cursorOverlay.querySelectorAll(".line-mark-cursor-move-arrow"));
          }

          let sidePanel = doc.getElementById("line-mark-side-zoom");
          let sidePanelCanvas = doc.getElementById("line-mark-side-zoom-canvas");
          const staleStagePanel = window.parent.document.getElementById("line-mark-stage-image-zoom");
          if (staleStagePanel) {
            staleStagePanel.remove();
          }
          if (!sidePanel || !sidePanelCanvas) {
            sidePanel = doc.createElement("div");
            sidePanel.id = "line-mark-side-zoom";
            sidePanel.style.position = "fixed";
            sidePanel.style.right = "12px";
            sidePanel.style.top = "12px";
            sidePanel.style.width = "170px";
            sidePanel.style.height = "170px";
            sidePanel.style.border = "1px solid #00ffff";
            sidePanel.style.background = "rgba(0,0,0,0.72)";
            sidePanel.style.borderRadius = "8px";
            sidePanel.style.zIndex = "2147483647";
            sidePanel.style.pointerEvents = "none";
            sidePanel.style.display = "none";
            sidePanelCanvas = doc.createElement("canvas");
            sidePanelCanvas.id = "line-mark-side-zoom-canvas";
            sidePanelCanvas.width = 168;
            sidePanelCanvas.height = 168;
            sidePanelCanvas.style.width = "168px";
            sidePanelCanvas.style.height = "168px";
            sidePanelCanvas.style.display = "block";
            sidePanel.appendChild(sidePanelCanvas);
            doc.body.appendChild(sidePanel);
          }

          const lensContext = lens.getContext("2d");
          const sideContext = sidePanelCanvas.getContext("2d");
          if (!lensContext || !sideContext || !sourceImageUrl) return;

          const providedImage = new Image();
          providedImage.src = sourceImageUrl;
          providedImage.onload = () => {
            paintDrawableBackground(providedImage);
            const zoom = zoomFactor;
            const radius = 30;
            const getCanvasPoint = (clientX, clientY, targetRect) => ({
              x: clientX - targetRect.left,
              y: clientY - targetRect.top,
            });
            const findNearestPointIndex = (canvasPoint) => {
              if (!Array.isArray(pointList) || !canvasPoint) return -1;
              let nearestIndex = -1;
              let nearestDistance = Number.POSITIVE_INFINITY;
              pointList.forEach((pointNode, index) => {
                if (!Array.isArray(pointNode) || pointNode.length < 2) return;
                const dx = canvasPoint.x - Number(pointNode[0] || 0);
                const dy = canvasPoint.y - Number(pointNode[1] || 0);
                const distance = Math.hypot(dx, dy);
                if (distance <= moveRadiusPx && distance < nearestDistance) {
                  nearestDistance = distance;
                  nearestIndex = index;
                }
              });
              return nearestIndex;
            };
            let cachedFabricCanvas = null;
            const getRawObjects = (candidate) => {
              if (!candidate) return [];
              if (typeof candidate.getObjects === "function") {
                try {
                  const objects = candidate.getObjects();
                  return Array.isArray(objects) ? objects : [];
                } catch (error) {}
              }
              if (Array.isArray(candidate._objects)) return candidate._objects;
              if (Array.isArray(candidate.objects)) return candidate.objects;
              return [];
            };
            const getPointObjects = (canvasLike) => {
              const objects = getRawObjects(canvasLike);
              return objects.filter((objectNode) => objectNode && (objectNode.type === "circle" || typeof objectNode.radius === "number"));
            };
            const isCanvasLikeWithPoints = (candidate) => {
              if (!candidate) return false;
              return getPointObjects(candidate).length > 0;
            };
            const getFabricCanvas = () => {
              if (cachedFabricCanvas) return cachedFabricCanvas;
              const candidateList = [
                upperCanvas && upperCanvas.__canvas,
                upperCanvas && upperCanvas.__fabric,
                upperCanvas && upperCanvas.fabric,
                upperCanvas && upperCanvas._fabricCanvas,
                lowerCanvas && lowerCanvas.__canvas,
                lowerCanvas && lowerCanvas.__fabric,
                lowerCanvas && lowerCanvas.fabric,
                lowerCanvas && lowerCanvas._fabricCanvas,
                frame.contentWindow && frame.contentWindow.__canvas,
                frame.contentWindow && frame.contentWindow._canvas,
                frame.contentWindow && frame.contentWindow.canvas,
                frame.contentWindow && frame.contentWindow.fabricCanvas,
              ];
              for (let index = 0; index < candidateList.length; index += 1) {
                if (isCanvasLikeWithPoints(candidateList[index])) {
                  cachedFabricCanvas = candidateList[index];
                  return cachedFabricCanvas;
                }
              }
              const windowKeys = Object.keys(frame.contentWindow || {}).filter((key) => key.toLowerCase().includes("canvas"));
              for (let index = 0; index < windowKeys.length; index += 1) {
                const candidate = frame.contentWindow[windowKeys[index]];
                if (isCanvasLikeWithPoints(candidate)) {
                  cachedFabricCanvas = candidate;
                  return cachedFabricCanvas;
                }
              }
              // Deep fallback: scan all top-level window values and one-level nested values.
              const windowObject = frame.contentWindow || {};
              const allKeys = Object.keys(windowObject);
              const matchesCanvasNode = (candidate) => (
                candidate &&
                (
                  candidate.upperCanvasEl === upperCanvas ||
                  candidate.lowerCanvasEl === lowerCanvas ||
                  candidate.contextTop?.canvas === upperCanvas ||
                  candidate.contextContainer?.canvas === lowerCanvas
                )
              );
              for (let index = 0; index < allKeys.length; index += 1) {
                let rootValue = null;
                try {
                  rootValue = windowObject[allKeys[index]];
                } catch (error) {
                  rootValue = null;
                }
                if (isCanvasLikeWithPoints(rootValue) && matchesCanvasNode(rootValue)) {
                  cachedFabricCanvas = rootValue;
                  return cachedFabricCanvas;
                }
                if (!rootValue || typeof rootValue !== "object") continue;
                let nestedKeys = [];
                try {
                  nestedKeys = Object.keys(rootValue);
                } catch (error) {
                  nestedKeys = [];
                }
                for (let nestedIndex = 0; nestedIndex < nestedKeys.length; nestedIndex += 1) {
                  let nestedValue = null;
                  try {
                    nestedValue = rootValue[nestedKeys[nestedIndex]];
                  } catch (error) {
                    nestedValue = null;
                  }
                  if (isCanvasLikeWithPoints(nestedValue) && matchesCanvasNode(nestedValue)) {
                    cachedFabricCanvas = nestedValue;
                    return cachedFabricCanvas;
                  }
                }
              }
              // Last-resort exhaustive scan for any object holding circle points.
              for (let index = 0; index < allKeys.length; index += 1) {
                let rootValue = null;
                try {
                  rootValue = windowObject[allKeys[index]];
                } catch (error) {
                  rootValue = null;
                }
                if (isCanvasLikeWithPoints(rootValue)) {
                  cachedFabricCanvas = rootValue;
                  return cachedFabricCanvas;
                }
                if (!rootValue || typeof rootValue !== "object") continue;
                let nestedKeys = [];
                try {
                  nestedKeys = Object.keys(rootValue);
                } catch (error) {
                  nestedKeys = [];
                }
                for (let nestedIndex = 0; nestedIndex < nestedKeys.length; nestedIndex += 1) {
                  let nestedValue = null;
                  try {
                    nestedValue = rootValue[nestedKeys[nestedIndex]];
                  } catch (error) {
                    nestedValue = null;
                  }
                  if (isCanvasLikeWithPoints(nestedValue)) {
                    cachedFabricCanvas = nestedValue;
                    return cachedFabricCanvas;
                  }
                }
              }
              // Deep recursive fallback with cycle protection.
              const root = frame.contentWindow || {};
              const visited = new WeakSet();
              const queue = [root];
              let scanned = 0;
              const MAX_SCAN_NODES = 5000;
              while (queue.length > 0 && scanned < MAX_SCAN_NODES) {
                const currentNode = queue.shift();
                if (!currentNode || (typeof currentNode !== "object" && typeof currentNode !== "function")) continue;
                if (visited.has(currentNode)) continue;
                visited.add(currentNode);
                scanned += 1;
                if (isCanvasLikeWithPoints(currentNode)) {
                  cachedFabricCanvas = currentNode;
                  return cachedFabricCanvas;
                }
                let childKeys = [];
                try {
                  childKeys = Object.keys(currentNode);
                } catch (error) {
                  childKeys = [];
                }
                for (let childIndex = 0; childIndex < childKeys.length; childIndex += 1) {
                  let childValue = null;
                  try {
                    childValue = currentNode[childKeys[childIndex]];
                  } catch (error) {
                    childValue = null;
                  }
                  if (!childValue) continue;
                  if (typeof childValue === "object" || typeof childValue === "function") {
                    queue.push(childValue);
                  }
                }
              }
              return null;
            };
            const renderFabricCanvas = (fabricCanvas) => {
              if (!fabricCanvas) return;
              if (typeof fabricCanvas.requestRenderAll === "function") {
                fabricCanvas.requestRenderAll();
                return;
              }
              if (typeof fabricCanvas.renderAll === "function") {
                fabricCanvas.renderAll();
              }
            };
            const setFabricPointCenter = (pointObject, canvasX, canvasY) => {
              if (!pointObject || typeof pointObject.set !== "function") return;
              const radiusValue = Number(pointObject.radius || 0);
              const originX = String(pointObject.originX || "left").toLowerCase();
              const originY = String(pointObject.originY || "top").toLowerCase();
              let leftValue = canvasX;
              let topValue = canvasY;
              if (originX === "left") leftValue = canvasX - radiusValue;
              else if (originX === "right") leftValue = canvasX + radiusValue;
              if (originY === "top") topValue = canvasY - radiusValue;
              else if (originY === "bottom") topValue = canvasY + radiusValue;
              pointObject.set({ left: leftValue, top: topValue });
              if (typeof pointObject.setCoords === "function") pointObject.setCoords();
            };
            const getGlobalDragState = () => {
              const state = window.parent.__lineMarkDragState;
              if (!state || typeof state !== "object") {
                return { active: false, index: -1, startMouse: null, startPoint: null };
              }
              return state;
            };
            const setGlobalDragState = (nextState) => {
              window.parent.__lineMarkDragState = nextState;
            };
            let dragPointIndex = -1;
            let dragStartMouse = null;
            let dragStartPoint = null;
            const restoredDragState = getGlobalDragState();
            if (restoredDragState.active) {
              dragPointIndex = Number(restoredDragState.index ?? -1);
              dragStartMouse = restoredDragState.startMouse || null;
              dragStartPoint = restoredDragState.startPoint || null;
            }
            let synthesizingPointPlacement = false;
            const prevMove = window.__lineMarkMoveHandler;
            const prevPointerMove = window.__lineMarkPointerMoveHandler;
            const prevDown = window.__lineMarkDownHandler;
            const prevUp = window.__lineMarkUpHandler;
            const prevEnter = window.__lineMarkCanvasEnterHandler;
            const prevLeave = window.__lineMarkCanvasLeaveHandler;
            if (prevMove) doc.removeEventListener("mousemove", prevMove, true);
            if (prevPointerMove) doc.removeEventListener("pointermove", prevPointerMove, true);
            if (prevDown) doc.removeEventListener("mousedown", prevDown, true);
            if (prevUp) doc.removeEventListener("mouseup", prevUp, true);
            if (prevUp) window.removeEventListener("mouseup", prevUp, true);
            if (prevMove) window.removeEventListener("mousemove", prevMove, true);
            if (prevPointerMove) window.removeEventListener("pointermove", prevPointerMove, true);
            if (prevEnter) {
              upperCanvas.removeEventListener("mouseenter", prevEnter, true);
              if (lowerCanvas) lowerCanvas.removeEventListener("mouseenter", prevEnter, true);
            }
            if (prevLeave) {
              upperCanvas.removeEventListener("mouseleave", prevLeave, true);
              if (lowerCanvas) lowerCanvas.removeEventListener("mouseleave", prevLeave, true);
            }

            const updateCursor = (clientX, clientY, targetRect, insideCanvas) => {
              const setCursor = (cursorValue) => applyCursorStyle(cursorValue);
              if (!insideCanvas) {
                setCursor("default");
                return false;
              }
              const canvasX = clientX - targetRect.left;
              const canvasY = clientY - targetRect.top;
              const nearExistingPoint = Array.isArray(pointList) && pointList.some((pointNode) => {
                if (!Array.isArray(pointNode) || pointNode.length < 2) return false;
                const dx = canvasX - Number(pointNode[0] || 0);
                const dy = canvasY - Number(pointNode[1] || 0);
                return Math.hypot(dx, dy) <= moveRadiusPx;
              });
              setCursor(nearExistingPoint ? "move" : "crosshair");
              return nearExistingPoint;
            };

            const drawAt = (clientX, clientY) => {
              const targetRect = upperCanvas.getBoundingClientRect();
              sidePanel.style.left = `${Math.round(targetRect.right + 12)}px`;
              sidePanel.style.top = `${Math.round(targetRect.top)}px`;
              sidePanel.style.right = "auto";
              const inside =
                clientX >= targetRect.left &&
                clientX <= targetRect.right &&
                clientY >= targetRect.top &&
                clientY <= targetRect.bottom;
              const nearExistingPoint = updateCursor(clientX, clientY, targetRect, inside);
              const canvasPoint = getCanvasPoint(clientX, clientY, targetRect);
              const nearestIndex = findNearestPointIndex(canvasPoint);
              if (!inside) {
                lens.style.display = "none";
                sidePanel.style.display = "none";
                cursorOverlay.style.display = "none";
                return;
              }
              if (dragPointIndex >= 0 && dragStartMouse && dragStartPoint && Array.isArray(pointList[dragPointIndex])) {
                const dx = clientX - dragStartMouse.x;
                const dy = clientY - dragStartMouse.y;
                const nextX = Math.max(0, Math.min(targetRect.width, dragStartPoint.x + dx));
                const nextY = Math.max(0, Math.min(targetRect.height, dragStartPoint.y + dy));
                pointList[dragPointIndex][0] = nextX;
                pointList[dragPointIndex][1] = nextY;
                setGlobalDragState({
                  active: true,
                  index: dragPointIndex,
                  startMouse: dragStartMouse,
                  startPoint: dragStartPoint,
                });
              }
              cursorOverlay.style.left = `${clientX - 11.5}px`;
              cursorOverlay.style.top = `${clientY - 11.5}px`;
              const overlayColor = "rgb(0,255,255)";
              if (cursorOverlayHorizontal) cursorOverlayHorizontal.style.background = overlayColor;
              if (cursorOverlayVertical) cursorOverlayVertical.style.background = overlayColor;
              const showMoveState = dragPointIndex >= 0 || nearExistingPoint;
              if (cursorOverlayHorizontal) cursorOverlayHorizontal.style.display = showMoveState ? "none" : "block";
              if (cursorOverlayVertical) cursorOverlayVertical.style.display = showMoveState ? "none" : "block";
              cursorOverlayMoveArrows.forEach((arrow) => {
                arrow.style.display = showMoveState ? "block" : "none";
              });
              cursorOverlay.style.transform = "scale(1)";
              cursorOverlay.style.display = "block";

              const sxScale = providedImage.naturalWidth / Math.max(1, targetRect.width);
              const syScale = providedImage.naturalHeight / Math.max(1, targetRect.height);
              const sample = (radius * 2) / zoom;
              // Sub-pixel bias keeps zoom sampling aligned with the custom cursor center.
              const sampleBiasPx = -0.5;
              const sampleX = (clientX - targetRect.left + sampleBiasPx) * sxScale;
              const sampleY = (clientY - targetRect.top + sampleBiasPx) * syScale;
              const sampleW = Math.max(2, sample * sxScale);
              const sampleH = Math.max(2, sample * syScale);
              const srcX = sampleX - sampleW / 2;
              const srcY = sampleY - sampleH / 2;
              const srcX0 = Math.max(0, srcX);
              const srcY0 = Math.max(0, srcY);
              const srcX1 = Math.min(providedImage.naturalWidth, srcX + sampleW);
              const srcY1 = Math.min(providedImage.naturalHeight, srcY + sampleH);
              const srcW = Math.max(0, srcX1 - srcX0);
              const srcH = Math.max(0, srcY1 - srcY0);
              const destLensSize = radius * 2;
              const dstX = (Math.max(0, srcX0 - srcX) / sampleW) * destLensSize;
              const dstY = (Math.max(0, srcY0 - srcY) / sampleH) * destLensSize;
              const dstW = (srcW / sampleW) * destLensSize;
              const dstH = (srcH / sampleH) * destLensSize;

              lens.style.left = `${clientX - radius}px`;
              lens.style.top = `${clientY - radius}px`;
              lens.style.display = "none";
              sidePanel.style.display = "block";

              lensContext.clearRect(0, 0, lens.width, lens.height);

              sideContext.clearRect(0, 0, sidePanelCanvas.width, sidePanelCanvas.height);
              sideContext.fillStyle = "rgba(0,0,0,0.55)";
              sideContext.fillRect(0, 0, sidePanelCanvas.width, sidePanelCanvas.height);
              sideContext.imageSmoothingEnabled = false;
              if (srcW > 0 && srcH > 0) {
                sideContext.drawImage(
                  providedImage,
                  srcX0,
                  srcY0,
                  srcW,
                  srcH,
                  (Math.max(0, srcX0 - srcX) / sampleW) * sidePanelCanvas.width,
                  (Math.max(0, srcY0 - srcY) / sampleH) * sidePanelCanvas.height,
                  (srcW / sampleW) * sidePanelCanvas.width,
                  (srcH / sampleH) * sidePanelCanvas.height
                );
              }
              sideContext.strokeStyle = "#00ffff";
              sideContext.lineWidth = 1;
              sideContext.lineCap = "round";
              sideContext.lineJoin = "round";
              sideContext.beginPath();
              sideContext.moveTo(sidePanelCanvas.width / 2 - 10, sidePanelCanvas.height / 2);
              sideContext.lineTo(sidePanelCanvas.width / 2 + 10, sidePanelCanvas.height / 2);
              sideContext.moveTo(sidePanelCanvas.width / 2, sidePanelCanvas.height / 2 - 10);
              sideContext.lineTo(sidePanelCanvas.width / 2, sidePanelCanvas.height / 2 + 10);
              sideContext.stroke();
            };

            window.__lineMarkMoveHandler = (event) => {
              if (synthesizingPointPlacement) return;
              drawAt(event.clientX, event.clientY);
            };
            window.__lineMarkPointerMoveHandler = (event) => {
              if (synthesizingPointPlacement) return;
              drawAt(event.clientX, event.clientY);
            };
            window.__lineMarkDownHandler = (event) => {
              if (synthesizingPointPlacement) return;
              const targetRect = upperCanvas.getBoundingClientRect();
              const inside =
                event.clientX >= targetRect.left &&
                event.clientX <= targetRect.right &&
                event.clientY >= targetRect.top &&
                event.clientY <= targetRect.bottom;
              if (inside) {
                const canvasPoint = getCanvasPoint(event.clientX, event.clientY, targetRect);
                const nearestIndex = findNearestPointIndex(canvasPoint);
                if (nearestIndex >= 0) {
                  dragPointIndex = nearestIndex;
                  dragStartMouse = { x: event.clientX, y: event.clientY };
                  dragStartPoint = {
                    x: Number(pointList[nearestIndex][0] || canvasPoint.x),
                    y: Number(pointList[nearestIndex][1] || canvasPoint.y),
                  };
                  setGlobalDragState({
                    active: true,
                    index: dragPointIndex,
                    startMouse: dragStartMouse,
                    startPoint: dragStartPoint,
                  });
                  if (event && typeof event.preventDefault === "function") event.preventDefault();
                  if (event && typeof event.stopPropagation === "function") event.stopPropagation();
                }
              }
              drawAt(event.clientX, event.clientY);
            };
            const handlePointerRelease = (event) => {
              if (synthesizingPointPlacement) return;
              if (dragPointIndex >= 0) {
                const targetRect = upperCanvas.getBoundingClientRect();
                const inside =
                  event.clientX >= targetRect.left &&
                  event.clientX <= targetRect.right &&
                  event.clientY >= targetRect.top &&
                  event.clientY <= targetRect.bottom;
                if (inside) {
                  const releaseCanvasPoint = Array.isArray(pointList[dragPointIndex])
                    ? {
                        x: Math.max(0, Math.min(targetRect.width, event.clientX - targetRect.left)),
                        y: Math.max(0, Math.min(targetRect.height, event.clientY - targetRect.top)),
                      }
                    : getCanvasPoint(event.clientX, event.clientY, targetRect);
                  const startCanvasPoint = dragStartPoint
                    ? { x: Number(dragStartPoint.x || 0), y: Number(dragStartPoint.y || 0) }
                    : releaseCanvasPoint;
                  const dispatchAtCanvasPoint = (canvasPoint) => {
                    const canvasX = Number(canvasPoint.x || 0);
                    const canvasY = Number(canvasPoint.y || 0);
                    const clientX = targetRect.left + canvasX;
                    const clientY = targetRect.top + canvasY;
                    const pointerInit = {
                      bubbles: true,
                      cancelable: true,
                      view: frame.contentWindow,
                      clientX,
                      clientY,
                      button: 0,
                    };
                    const targetNode = doc.elementFromPoint(clientX, clientY) || upperCanvas;
                    const dispatchSequence = (node) => {
                      if (!node || typeof node.dispatchEvent !== "function") return;
                      try {
                        if (typeof frame.contentWindow.PointerEvent === "function") {
                          node.dispatchEvent(new PointerEvent("pointerdown", pointerInit));
                          node.dispatchEvent(new PointerEvent("pointerup", pointerInit));
                        }
                      } catch (error) {}
                      try { node.dispatchEvent(new MouseEvent("mousedown", pointerInit)); } catch (error) {}
                      try { node.dispatchEvent(new MouseEvent("mouseup", pointerInit)); } catch (error) {}
                      try { node.dispatchEvent(new MouseEvent("click", pointerInit)); } catch (error) {}
                    };
                    dispatchSequence(targetNode);
                    if (targetNode !== upperCanvas) dispatchSequence(upperCanvas);
                    if (lowerCanvas && targetNode !== lowerCanvas) dispatchSequence(lowerCanvas);
                    return { clientX, clientY, targetNode };
                  };
                  synthesizingPointPlacement = true;
                  try {
                    // Two-step signal: (1) source point click arms move, (2) destination click commits move.
                    dispatchAtCanvasPoint(startCanvasPoint);
                    dispatchAtCanvasPoint(releaseCanvasPoint);
                  } catch (error) {}
                  synthesizingPointPlacement = false;
                }
              }
              dragPointIndex = -1;
              dragStartMouse = null;
              dragStartPoint = null;
              setGlobalDragState({ active: false, index: -1, startMouse: null, startPoint: null });
              drawAt(event.clientX, event.clientY);
            };
            window.__lineMarkUpHandler = (event) => handlePointerRelease(event);
            window.__lineMarkCanvasEnterHandler = () => {
              applyCursorStyle("crosshair");
            };
            window.__lineMarkCanvasLeaveHandler = () => {
              applyCursorStyle("default");
              cursorOverlay.style.display = "none";
            };

            // Touch support: map touch events to the same mouse/pointer handlers.
            // On touchstart we show the zoom panel at the finger position so the user
            // can see exactly where the point will land before lifting their finger.
            // On touchend we commit the point (or drag) at the final touch position.
            // We suppress the default browser behaviour (scroll, zoom) while a finger
            // is inside the canvas so the page doesn't scroll mid-mark.
            let touchActive = false;
            let lastTouchClientX = 0;
            let lastTouchClientY = 0;
            const getTouchCoords = (event) => {
              const touch = event.changedTouches[0] || event.touches[0];
              if (!touch) return null;
              return { clientX: touch.clientX, clientY: touch.clientY };
            };
            const isTouchOnCanvas = (clientX, clientY) => {
              const targetRect = upperCanvas.getBoundingClientRect();
              return (
                clientX >= targetRect.left &&
                clientX <= targetRect.right &&
                clientY >= targetRect.top &&
                clientY <= targetRect.bottom
              );
            };
            window.__lineMarkTouchStartHandler = (event) => {
              if (synthesizingPointPlacement) return;
              const coords = getTouchCoords(event);
              if (!coords) return;
              if (!isTouchOnCanvas(coords.clientX, coords.clientY)) return;
              // Prevent scroll/pinch while the user is marking points on the canvas.
              event.preventDefault();
              touchActive = true;
              lastTouchClientX = coords.clientX;
              lastTouchClientY = coords.clientY;
              // Show the zoom lens at the touch point so the user can position precisely.
              drawAt(coords.clientX, coords.clientY);
              // Synthesise a mousedown so drag-detection can arm if touching a known point.
              const syntheticDown = {
                clientX: coords.clientX,
                clientY: coords.clientY,
                preventDefault: () => {},
                stopPropagation: () => {},
              };
              window.__lineMarkDownHandler(syntheticDown);
            };
            window.__lineMarkTouchMoveHandler = (event) => {
              if (synthesizingPointPlacement || !touchActive) return;
              const coords = getTouchCoords(event);
              if (!coords) return;
              event.preventDefault();
              lastTouchClientX = coords.clientX;
              lastTouchClientY = coords.clientY;
              // Update the zoom panel as the finger moves so users can fine-position.
              drawAt(coords.clientX, coords.clientY);
              // Drive the drag logic the same as mouse move.
              window.__lineMarkMoveHandler({ clientX: coords.clientX, clientY: coords.clientY });
            };
            window.__lineMarkTouchEndHandler = (event) => {
              if (synthesizingPointPlacement || !touchActive) return;
              touchActive = false;
              const coords = getTouchCoords(event) || { clientX: lastTouchClientX, clientY: lastTouchClientY };
              event.preventDefault();
              // Commit: synthesise a mouseup at the final touch position.
              handlePointerRelease({ clientX: coords.clientX, clientY: coords.clientY });
              // Hide the zoom panel a moment after the finger lifts.
              window.setTimeout(() => {
                sidePanel.style.display = "none";
                cursorOverlay.style.display = "none";
              }, 600);
            };
            const prevTouchStart = window.__lineMarkPrevTouchStart;
            const prevTouchMove = window.__lineMarkPrevTouchMove;
            const prevTouchEnd = window.__lineMarkPrevTouchEnd;
            if (prevTouchStart) {
              doc.removeEventListener("touchstart", prevTouchStart, true);
              upperCanvas.removeEventListener("touchstart", prevTouchStart, { passive: false });
            }
            if (prevTouchMove) {
              doc.removeEventListener("touchmove", prevTouchMove, true);
              upperCanvas.removeEventListener("touchmove", prevTouchMove, { passive: false });
            }
            if (prevTouchEnd) {
              doc.removeEventListener("touchend", prevTouchEnd, true);
              upperCanvas.removeEventListener("touchend", prevTouchEnd, { passive: false });
            }
            window.__lineMarkPrevTouchStart = window.__lineMarkTouchStartHandler;
            window.__lineMarkPrevTouchMove = window.__lineMarkTouchMoveHandler;
            window.__lineMarkPrevTouchEnd = window.__lineMarkTouchEndHandler;
            // Attach at the canvas level (not passive) so preventDefault() works.
            upperCanvas.addEventListener("touchstart", window.__lineMarkTouchStartHandler, { passive: false, capture: true });
            upperCanvas.addEventListener("touchmove", window.__lineMarkTouchMoveHandler, { passive: false, capture: true });
            upperCanvas.addEventListener("touchend", window.__lineMarkTouchEndHandler, { passive: false, capture: true });
            // Also catch touches that start inside but drift outside the canvas element.
            doc.addEventListener("touchmove", window.__lineMarkTouchMoveHandler, { passive: false, capture: true });
            doc.addEventListener("touchend", window.__lineMarkTouchEndHandler, { passive: false, capture: true });

            doc.addEventListener("mousemove", window.__lineMarkMoveHandler, true);
            doc.addEventListener("pointermove", window.__lineMarkPointerMoveHandler, true);
            doc.addEventListener("mousedown", window.__lineMarkDownHandler, true);
            doc.addEventListener("mouseup", window.__lineMarkUpHandler, true);
            window.addEventListener("mousemove", window.__lineMarkMoveHandler, true);
            window.addEventListener("pointermove", window.__lineMarkPointerMoveHandler, true);
            window.addEventListener("mouseup", window.__lineMarkUpHandler, true);
            upperCanvas.addEventListener("mouseenter", window.__lineMarkCanvasEnterHandler, true);
            upperCanvas.addEventListener("mouseleave", window.__lineMarkCanvasLeaveHandler, true);
            if (lowerCanvas) {
              lowerCanvas.addEventListener("mouseenter", window.__lineMarkCanvasEnterHandler, true);
              lowerCanvas.addEventListener("mouseleave", window.__lineMarkCanvasLeaveHandler, true);
            }
            // Custom drag/drop support intentionally disabled.
          };
        } catch (error) {}
      });
      setTimeout(applyCanvasEnhancements, 1200);
    })();
    </script>
    """
    return (
        script.replace("__SOURCE_IMAGE_URL__", json.dumps(source_image_url))
        .replace("__ZOOM_FACTOR__", str(int(zoom_factor)))
        .replace("__POINTS__", json.dumps(points or []))
        .replace("__MOVE_RADIUS_PX__", json.dumps(float(move_radius_px)))
    )


