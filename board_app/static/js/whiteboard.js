// Fixed whiteboard.js - Main whiteboard functionality
class WhiteboardClient {
    constructor(boardId) {
        this.boardId = boardId;
        this.canvas = document.getElementById('whiteboard-canvas');
        this.ctx = this.canvas.getContext('2d');
        this.socket = null;
        
        // Drawing state
        this.isDrawing = false;
        this.currentTool = 'pen';
        this.currentColor = '#000000';
        this.currentBrushSize = 3;
        this.canDraw = document.querySelector('meta[name="can-draw"]').content === 'true';
        
        // Drawing data
        this.startX = 0;
        this.startY = 0;
        this.currentPath = [];
        
        // User cursors
        this.userCursors = new Map();
        
        // Board state
        this.boardActions = [];
        
        // Initialize
        this.setupCanvas();
        this.setupEventListeners();
        this.connectSocket();
        this.startHeartbeat();
    }

    setupCanvas() {
        // Set canvas size
        const container = document.getElementById('whiteboard-container');
        this.canvas.width = container.offsetWidth;
        this.canvas.height = container.offsetHeight || 600;
        
        // Set drawing defaults
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = this.currentColor;
        this.ctx.lineWidth = this.currentBrushSize;
    }

    setupEventListeners() {
        // Canvas events
        this.canvas.addEventListener('mousedown', this.handleMouseDown.bind(this));
        this.canvas.addEventListener('mousemove', this.handleMouseMove.bind(this));
        this.canvas.addEventListener('mouseup', this.handleMouseUp.bind(this));
        this.canvas.addEventListener('mouseleave', this.handleMouseUp.bind(this));
        
        // Touch events for mobile
        this.canvas.addEventListener('touchstart', this.handleTouchStart.bind(this));
        this.canvas.addEventListener('touchmove', this.handleTouchMove.bind(this));
        this.canvas.addEventListener('touchend', this.handleTouchEnd.bind(this));
        
        // Cursor tracking (throttled)
        const throttledCursorUpdate = this.throttle(this.sendCursorPosition.bind(this), 100);
        this.canvas.addEventListener('mousemove', throttledCursorUpdate);
        
        // Tool selection
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.selectTool(e.target.closest('.tool-btn').dataset.tool);
            });
        });
        
        // Color selection
        document.querySelectorAll('.color-option').forEach(option => {
            option.addEventListener('click', (e) => {
                this.selectColor(e.target.dataset.color);
            });
        });
        
        // Brush size
        const brushSizeSlider = document.getElementById('brush-size');
        const brushSizeValue = document.getElementById('brush-size-value');
        if (brushSizeSlider) {
            brushSizeSlider.addEventListener('input', (e) => {
                this.currentBrushSize = parseInt(e.target.value);
                brushSizeValue.textContent = this.currentBrushSize;
                this.ctx.lineWidth = this.currentBrushSize;
            });
        }
        
        // Clear board
        const clearBtn = document.getElementById('clear-board');
        if (clearBtn) {
            clearBtn.addEventListener('click', this.clearBoard.bind(this));
        }
        
        // Text tool modal
        const addTextBtn = document.getElementById('add-text');
        if (addTextBtn) {
            addTextBtn.addEventListener('click', this.addText.bind(this));
        }
        
        // Window resize
        window.addEventListener('resize', this.debounce(this.handleResize.bind(this), 250));
        
        // Select pen tool by default
        this.selectTool('pen');
    }

    connectSocket() {
        
        this.socket = io({
            query: {
                board_id: this.boardId
            },
            transports: ['websocket', 'polling']
        });

        // Connection events
        this.socket.on('connect', () => {
            this.showConnectionStatus(true);
            this.requestUsers();
        });

        this.socket.on('disconnect', (reason) => {
            this.showConnectionStatus(false);
        });

        this.socket.on('connect_error', (error) => {
            this.showConnectionStatus(false);
        });

        // Board events
        this.socket.on('board_state', (data) => {
            this.loadBoardState(data.state);
        });

        this.socket.on('drawing_action', (data) => {
            // Only apply actions from other users
            if (data.current_user !== this.getCurrentUsername()) {
                this.executeDrawingAction(data.action);
                this.boardActions.push(data.action);
            }
            this.logActivity(`${data.current_user} drew on the board`);
        });

        // User events
        this.socket.on('user_joined', (data) => {
            this.updateUsersList(data.users);
            this.logActivity(`${data.username} joined the board`);
        });

        this.socket.on('user_left', (data) => {
            this.updateUsersList(data.users);
            this.removeUserCursor(data.username);
            this.logActivity(`${data.username} left the board`);
        });

        this.socket.on('active_users', (data) => {
            this.updateUsersList(data.users);
        });

        this.socket.on('cursor_position', (data) => {
            this.updateUserCursor(data.user, data.x, data.y);
        });

        this.socket.on('heartbeat_response', () => {
            this.showConnectionStatus(true);
        });

        this.socket.on('error', (data) => {
            this.showError(data.message);
        });
    }

    // Drawing event handlers
    handleMouseDown(e) {
        if (!this.canDraw) return;
        
        const rect = this.canvas.getBoundingClientRect();
        this.startX = e.clientX - rect.left;
        this.startY = e.clientY - rect.top;
        this.isDrawing = true;

        this.beginPath();
    }

    handleMouseMove(e) {
        if (!this.isDrawing || !this.canDraw) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;
        
        this.continuePath(currentX, currentY);
    }

    handleMouseUp(e) {
        if (!this.isDrawing || !this.canDraw) return;
        this.isDrawing = false;
        this.endPath();
    }

    // Touch event handlers
    handleTouchStart(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousedown', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.canvas.dispatchEvent(mouseEvent);
    }

    handleTouchMove(e) {
        e.preventDefault();
        const touch = e.touches[0];
        const mouseEvent = new MouseEvent('mousemove', {
            clientX: touch.clientX,
            clientY: touch.clientY
        });
        this.canvas.dispatchEvent(mouseEvent);
    }

    handleTouchEnd(e) {
        e.preventDefault();
        const mouseEvent = new MouseEvent('mouseup', {});
        this.canvas.dispatchEvent(mouseEvent);
    }

    // Drawing methods
    beginPath() {
        this.currentPath = [{x: this.startX, y: this.startY}];
        
        if (this.currentTool === 'text') {
            this.showTextModal(this.startX, this.startY);
            return;
        }
        
        this.ctx.beginPath();
        this.ctx.moveTo(this.startX, this.startY);
        
        if (this.currentTool === 'eraser') {
            this.ctx.globalCompositeOperation = 'destination-out';
        } else {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.strokeStyle = this.currentColor;
        }
        
        this.ctx.lineWidth = this.currentBrushSize;
    }

    continuePath(x, y) {
        this.currentPath.push({x, y});
        
        switch (this.currentTool) {
            case 'pen':
            case 'eraser':
                this.ctx.lineTo(x, y);
                this.ctx.stroke();
                break;
            case 'line':
                this.redrawAndPreview();
                this.drawLine(this.startX, this.startY, x, y);
                break;
            case 'rectangle':
                this.redrawAndPreview();
                this.drawRectangle(this.startX, this.startY, x, y);
                break;
            case 'circle':
                this.redrawAndPreview();
                this.drawCircle(this.startX, this.startY, x, y);
                break;
        }
    }

    endPath() {
        if (this.currentPath.length > 0) {
            const actionData = {
                action_type: this.currentTool,
                action_data: {
                    path: this.currentPath,
                    color: this.currentColor,
                    brushSize: this.currentBrushSize,
                    startX: this.startX,
                    startY: this.startY
                },
                action_id: this.generateActionId()
            };

            this.socket.emit('drawing_action', actionData);
            
            // Add to local state immediately
            const action = {
                action_type: this.currentTool,
                action_data: actionData.action_data,
                action_id: actionData.action_id,
                user_id: 'current_user'
            };
            this.boardActions.push(action);
        }
        
        this.currentPath = [];
        this.ctx.globalCompositeOperation = 'source-over';
    }

    // Shape drawing methods
    drawLine(x1, y1, x2, y2) {
        this.ctx.beginPath();
        this.ctx.moveTo(x1, y1);
        this.ctx.lineTo(x2, y2);
        this.ctx.stroke();
    }

    drawRectangle(x1, y1, x2, y2) {
        const width = x2 - x1;
        const height = y2 - y1;
        this.ctx.beginPath();
        this.ctx.rect(x1, y1, width, height);
        this.ctx.stroke();
    }

    drawCircle(x1, y1, x2, y2) {
        const radius = Math.sqrt(Math.pow(x2 - x1, 2) + Math.pow(y2 - y1, 2));
        this.ctx.beginPath();
        this.ctx.arc(x1, y1, radius, 0, 2 * Math.PI);
        this.ctx.stroke();
    }

    drawText(x, y, text, color, size) {
        this.ctx.font = `${size}px Arial`;
        this.ctx.fillStyle = color;
        this.ctx.fillText(text, x, y);
    }

    // Tool and color selection
    selectTool(tool) {
        this.currentTool = tool;
        
        // Update UI
        document.querySelectorAll('.tool-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const toolBtn = document.querySelector(`[data-tool="${tool}"]`);
        if (toolBtn) {
            toolBtn.classList.add('active');
        }
        
        // Update cursor
        this.canvas.style.cursor = 'crosshair';
    }

    selectColor(color) {
        this.currentColor = color;
        this.ctx.strokeStyle = color;
        
        // Update UI
        document.querySelectorAll('.color-option').forEach(option => {
            option.classList.remove('active');
        });
        const colorOption = document.querySelector(`[data-color="${color}"]`);
        if (colorOption) {
            colorOption.classList.add('active');
        }
    }

    // Board state management
    loadBoardState(state) {
        this.boardActions = [...state];
        this.redrawBoard();
    }

    redrawBoard() {
        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Execute all actions in order
        this.boardActions.forEach(action => {
            this.executeDrawingAction(action);
        });
    }

    redrawAndPreview() {
        // Redraw all existing actions
        this.redrawBoard();
        
        // Set current drawing style for preview
        this.ctx.strokeStyle = this.currentColor;
        this.ctx.lineWidth = this.currentBrushSize;
        this.ctx.globalCompositeOperation = 'source-over';
    }

    executeDrawingAction(action) {
        if (!action || !action.action_data) {
            return;
        }

        const { action_type, action_data } = action;
        
        // Save current context
        const currentColor = this.ctx.strokeStyle;
        const currentLineWidth = this.ctx.lineWidth;
        const currentCompositeOperation = this.ctx.globalCompositeOperation;
        
        // Handle clear action
        if (action_type === 'clear') {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            this.boardActions = [];
            return;
        }
        
        // Set action properties
        this.ctx.strokeStyle = action_data.color || '#000000';
        this.ctx.lineWidth = action_data.brushSize || 3;
        this.ctx.globalCompositeOperation = 'source-over';
        
        try {
            switch (action_type) {
                case 'pen':
                    this.executePathAction(action_data.path);
                    break;
                case 'eraser':
                    this.ctx.globalCompositeOperation = 'destination-out';
                    this.executePathAction(action_data.path);
                    break;
                case 'line':
                    if (action_data.path && action_data.path.length > 0) {
                        const lastPoint = action_data.path[action_data.path.length - 1];
                        this.drawLine(action_data.startX, action_data.startY, lastPoint.x, lastPoint.y);
                    }
                    break;
                case 'rectangle':
                    if (action_data.path && action_data.path.length > 0) {
                        const lastPoint = action_data.path[action_data.path.length - 1];
                        this.drawRectangle(action_data.startX, action_data.startY, lastPoint.x, lastPoint.y);
                    }
                    break;
                case 'circle':
                    if (action_data.path && action_data.path.length > 0) {
                        const lastPoint = action_data.path[action_data.path.length - 1];
                        this.drawCircle(action_data.startX, action_data.startY, lastPoint.x, lastPoint.y);
                    }
                    break;
                case 'text':
                    if (action_data.text) {
                        this.drawText(action_data.x, action_data.y, action_data.text, action_data.color, action_data.size);
                    }
                    break;
                default:
            }
        } catch (error) {
            console.error('Error executing drawing action:', error, action);
        }
        
        // Restore context
        this.ctx.strokeStyle = currentColor;
        this.ctx.lineWidth = currentLineWidth;
        this.ctx.globalCompositeOperation = currentCompositeOperation;
    }

    executePathAction(path) {
        if (path && path.length > 0) {
            this.ctx.beginPath();
            this.ctx.moveTo(path[0].x, path[0].y);
            
            for (let i = 1; i < path.length; i++) {
                this.ctx.lineTo(path[i].x, path[i].y);
            }
            
            this.ctx.stroke();
        }
    }

    clearBoard() {
        if (confirm('Are you sure you want to clear the entire board? This cannot be undone.')) {
            const actionData = {
                action_type: 'clear',
                action_data: {},
                action_id: this.generateActionId()
            };
            this.socket.emit('drawing_action', actionData);
            
            // Clear locally immediately
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            this.boardActions = [];
        }
    }

    // Text functionality
    showTextModal(x, y) {
        this.textPosition = { x, y };
        const textModal = document.getElementById('textModal');
        if (textModal && typeof bootstrap !== 'undefined') {
            const modal = new bootstrap.Modal(textModal);
            modal.show();
        } else {
            // Fallback for simple text input
            const text = prompt('Enter text:');
            if (text) {
                this.addTextDirectly(text, x, y);
            }
        }
    }

    addText() {
        const textInput = document.getElementById('text-input');
        const text = textInput ? textInput.value.trim() : '';
        
        if (text && this.textPosition) {
            this.addTextDirectly(text, this.textPosition.x, this.textPosition.y);
            
            if (textInput) textInput.value = '';
            
            // Close modal if bootstrap is available
            const textModal = document.getElementById('textModal');
            if (textModal && typeof bootstrap !== 'undefined') {
                const modal = bootstrap.Modal.getInstance(textModal);
                if (modal) modal.hide();
            }
        }
    }

    addTextDirectly(text, x, y) {
        const actionData = {
            action_type: 'text',
            action_data: {
                text: text,
                x: x,
                y: y,
                color: this.currentColor,
                size: this.currentBrushSize * 4
            },
            action_id: this.generateActionId()
        };
        
        this.socket.emit('drawing_action', actionData);
        
        // Draw locally immediately
        this.drawText(x, y, text, this.currentColor, this.currentBrushSize * 4);
        
        // Add to local state
        this.boardActions.push({
            action_type: 'text',
            action_data: actionData.action_data,
            action_id: actionData.action_id
        });
    }

    // User management
    updateUsersList(users) {
        const usersList = document.getElementById('users-list');
        if (usersList) {
            usersList.innerHTML = users.map(username => `
                <div class="user-item mb-1">
                    <span class="badge bg-success">●</span> ${username}
                </div>
            `).join('');
        }
    }

    // Cursor management
    sendCursorPosition(e) {
        if (!this.socket || !this.socket.connected) return;
        
        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        
        this.socket.emit('cursor_position', { x, y });
    }

    updateUserCursor(username, x, y) {
        let cursor = this.userCursors.get(username);
        
        if (!cursor) {
            cursor = this.createUserCursor(username);
            this.userCursors.set(username, cursor);
        }
        
        cursor.element.style.left = x + 'px';
        cursor.element.style.top = y + 'px';
        cursor.label.style.left = (x + 15) + 'px';
        cursor.label.style.top = (y - 25) + 'px';
    }

    createUserCursor(username) {
        const container = document.getElementById('whiteboard-container');
        
        // Create cursor element
        const cursorElement = document.createElement('div');
        cursorElement.className = 'user-cursor';
        cursorElement.style.backgroundColor = this.getUserColor(username);
        
        // Create label element
        const labelElement = document.createElement('div');
        labelElement.className = 'user-label';
        labelElement.textContent = username;
        labelElement.style.backgroundColor = this.getUserColor(username);
        
        container.appendChild(cursorElement);
        container.appendChild(labelElement);
        
        return {
            element: cursorElement,
            label: labelElement
        };
    }

    removeUserCursor(username) {
        const cursor = this.userCursors.get(username);
        if (cursor) {
            cursor.element.remove();
            cursor.label.remove();
            this.userCursors.delete(username);
        }
    }

    getUserColor(username) {
        // Generate a consistent color for each user based on username
        let hash = 0;
        for (let i = 0; i < username.length; i++) {
            hash = username.charCodeAt(i) + ((hash << 5) - hash);
        }
        const hue = Math.abs(hash) % 360;
        return `hsl(${hue}, 70%, 50%)`;
    }

    // Utility methods
    requestUsers() {
        if (this.socket && this.socket.connected) {
            this.socket.emit('request_users');
        }
    }

    startHeartbeat() {
        setInterval(() => {
            if (this.socket && this.socket.connected) {
                this.socket.emit('heartbeat');
            }
        }, 30000); // Send heartbeat every 30 seconds
    }

    handleResize() {
        const container = document.getElementById('whiteboard-container');
        const oldWidth = this.canvas.width;
        const oldHeight = this.canvas.height;
        
        this.canvas.width = container.offsetWidth;
        this.canvas.height = container.offsetHeight || 600;
        
        // Redraw the board after resize
        this.redrawBoard();
    }

    getCurrentUsername() {
        // Get username from various possible sources
        if (window.currentUsername) {
            return window.currentUsername;
        }
        
        // Try to get from meta tag
        const userMeta = document.querySelector('meta[name="current-user"]');
        if (userMeta) {
            return userMeta.content;
        }
        
        // Try to get from global variable or other sources
        return 'unknown';
    }

    logActivity(message) {
        const activityLog = document.getElementById('activity-log');
        if (activityLog) {
            const timestamp = new Date().toLocaleTimeString();
            
            const logEntry = document.createElement('div');
            logEntry.className = 'activity-entry small text-muted mb-1';
            logEntry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;
            
            activityLog.appendChild(logEntry);
            activityLog.scrollTop = activityLog.scrollHeight;
            
            // Limit activity log entries
            const entries = activityLog.children;
            if (entries.length > 50) {
                activityLog.removeChild(entries[0]);
            }
        }
    }

    showConnectionStatus(connected) {
        // Add visual indicator for connection status
        let indicator = document.getElementById('connection-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'connection-indicator';
            indicator.style.cssText = `
                position: fixed;
                top: 10px;
                right: 10px;
                padding: 5px 10px;
                border-radius: 15px;
                font-size: 12px;
                z-index: 1000;
                transition: all 0.3s ease;
            `;
            document.body.appendChild(indicator);
        }
        
        if (connected) {
            indicator.textContent = '● Connected';
            indicator.style.backgroundColor = '#d4edda';
            indicator.style.color = '#155724';
            indicator.style.border = '1px solid #c3e6cb';
        } else {
            indicator.textContent = '● Disconnected';
            indicator.style.backgroundColor = '#f8d7da';
            indicator.style.color = '#721c24';
            indicator.style.border = '1px solid #f5c6cb';
        }
    }

    showError(message) {
        console.error('Error:', message);
        
        // Try to show bootstrap toast if available
        if (typeof bootstrap !== 'undefined') {
            this.showBootstrapToast(message, 'error');
            return;
        }
        
        // Fallback to simple alert
        alert('Error: ' + message);
    }

    showBootstrapToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${type === 'error' ? 'danger' : 'primary'} border-0`;
        toast.setAttribute('role', 'alert');
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        // Add to toast container or create one
        let toastContainer = document.getElementById('toast-container');
        if (!toastContainer) {
            toastContainer = document.createElement('div');
            toastContainer.id = 'toast-container';
            toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
            toastContainer.style.zIndex = '1055';
            document.body.appendChild(toastContainer);
        }
        
        toastContainer.appendChild(toast);
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Remove toast element after it's hidden
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
    }

    // Utility functions
    generateActionId() {
        return Date.now().toString(36) + Math.random().toString(36).substr(2);
    }

    debounce(func, wait) {
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

    throttle(func, limit) {
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
}

// Initialize whiteboard function
function initializeWhiteboard(boardId) {
    window.whiteboard = new WhiteboardClient(boardId);
    
    // Set current username if available
    const currentUserElement = document.querySelector('[data-current-user]');
    if (currentUserElement) {
        window.currentUsername = currentUserElement.dataset.currentUser;
    }
    
    return window.whiteboard;
}

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { WhiteboardClient, initializeWhiteboard };
}