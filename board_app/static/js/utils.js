// Utility functions for the whiteboard application

class DrawingUtils {
    /**
     * Draw a line on the canvas
     */
    static drawLine(ctx, actionData) {
        ctx.beginPath();
        ctx.moveTo(actionData.startX, actionData.startY);
        ctx.lineTo(actionData.endX, actionData.endY);
        ctx.strokeStyle = actionData.color || '#000';
        ctx.lineWidth = actionData.lineWidth || 2;
        ctx.lineCap = 'round';
        ctx.stroke();
    }

    /**
     * Draw a freehand path
     */
    static drawPath(ctx, actionData) {
        if (!actionData.points || actionData.points.length < 2) return;

        ctx.beginPath();
        ctx.moveTo(actionData.points[0].x, actionData.points[0].y);

        for (let i = 1; i < actionData.points.length; i++) {
            ctx.lineTo(actionData.points[i].x, actionData.points[i].y);
        }

        ctx.strokeStyle = actionData.color || '#000';
        ctx.lineWidth = actionData.lineWidth || 2;
        ctx.lineCap = 'round';
        ctx.lineJoin = 'round';
        ctx.stroke();
    }

    /**
     * Draw a rectangle
     */
    static drawRectangle(ctx, actionData) {
        ctx.strokeStyle = actionData.color || '#000';
        ctx.lineWidth = actionData.lineWidth || 2;
        ctx.strokeRect(
            actionData.startX,
            actionData.startY,
            actionData.endX - actionData.startX,
            actionData.endY - actionData.startY
        );
    }

    /**
     * Draw a circle
     */
    static drawCircle(ctx, actionData) {
        const radius = Math.sqrt(
            Math.pow(actionData.endX - actionData.startX, 2) +
            Math.pow(actionData.endY - actionData.startY, 2)
        );

        ctx.beginPath();
        ctx.arc(actionData.startX, actionData.startY, radius, 0, 2 * Math.PI);
        ctx.strokeStyle = actionData.color || '#000';
        ctx.lineWidth = actionData.lineWidth || 2;
        ctx.stroke();
    }

    /**
     * Draw text
     */
    static drawText(ctx, actionData) {
        ctx.font = `${actionData.fontSize || 16}px Arial`;
        ctx.fillStyle = actionData.color || '#000';
        ctx.fillText(actionData.text || '', actionData.x, actionData.y);
    }

    /**
     * Clear a specific area or the entire canvas
     */
    static clearArea(ctx, actionData, canvas) {
        if (actionData.clearAll) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
        } else if (
            actionData.startX !== undefined && actionData.startY !== undefined &&
            actionData.endX !== undefined && actionData.endY !== undefined
        ) {
            ctx.clearRect(
                actionData.startX,
                actionData.startY,
                actionData.endX - actionData.startX,
                actionData.endY - actionData.startY
            );
        }
    }

    /**
     * Apply an action to the canvas
     */
    static applyActionToCanvas(ctx, action, canvas) {
        switch (action.action_type) {
            case 'draw':
                this.drawPath(ctx, action.action_data);
                break;
            case 'line':
                this.drawLine(ctx, action.action_data);
                break;
            case 'shape':
                if (action.action_data.shapeType === 'rectangle') {
                    this.drawRectangle(ctx, action.action_data);
                } else if (action.action_data.shapeType === 'circle') {
                    this.drawCircle(ctx, action.action_data);
                }
                break;
            case 'text':
                this.drawText(ctx, action.action_data);
                break;
            case 'erase':
                this.clearArea(ctx, action.action_data, canvas);
                break;
            case 'clear':
                this.clearArea(ctx, { clearAll: true }, canvas);
                break;
        }
    }

    /**
     * Generate a unique ID for actions
     */
    static generateActionId() {
        return 'action_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }

    /**
     * Get mouse position relative to canvas
     */
    static getMousePos(canvas, event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: event.clientX - rect.left,
            y: event.clientY - rect.top
        };
    }

    /**
     * Get touch position relative to canvas
     */
    static getTouchPos(canvas, event) {
        const rect = canvas.getBoundingClientRect();
        return {
            x: event.touches[0].clientX - rect.left,
            y: event.touches[0].clientY - rect.top
        };
    }
}

// Export for Node.js (optional, not needed in browser)
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { DrawingUtils };
}
function generateActionId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    }
}