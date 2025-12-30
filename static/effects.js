/**
 * YoYo Music Effects Library
 * Contains Canvas animations for Reactive Particles and Aurora effects.
 */

/* --- Reactive Background (Particles) --- */
class ReactiveParticles {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.particles = [];
        this.running = false;
        this.isPlaying = false;
        this.pulseBase = 1;
        this.pulseDir = 1;
        
        // Mobile detection
        this.isMobile = /iPhone|iPad|iPod|Android/i.test(navigator.userAgent);
        
        this.resize();
        window.addEventListener('resize', () => this.resize());
        
        // Initialize particles
        this.initParticles();
    }

    initParticles() {
        this.particles = [];
        const count = this.isMobile ? 40 : 150; 
        for (let i = 0; i < count; i++) {
            this.particles.push({
                x: Math.random() * this.width,
                y: Math.random() * this.height,
                size: Math.random() * 2 + 0.5,
                speedX: (Math.random() - 0.5) * 0.5,
                speedY: (Math.random() - 0.5) * 0.5,
                baseSpeedX: (Math.random() - 0.5) * 0.5,
                baseSpeedY: (Math.random() - 0.5) * 0.5,
                alpha: Math.random() * 0.5 + 0.1
            });
        }
    }

    resize() {
        this.width = window.innerWidth;
        this.height = window.innerHeight;
        this.canvas.width = this.width;
        this.canvas.height = this.height;
    }

    setPlaying(playing) {
        this.isPlaying = playing;
    }

    animate() {
        if (!this.running) return;
        
        // Clear canvas
        this.ctx.clearRect(0, 0, this.width, this.height);
        
        // Pulse logic (simulated beat)
        if (this.isPlaying) {
            this.pulseBase += 0.02 * this.pulseDir;
            if (this.pulseBase > 1.2) this.pulseDir = -1;
            if (this.pulseBase < 1.0) this.pulseDir = 1;
        } else {
            // Return to calm
            if (this.pulseBase > 1) this.pulseBase -= 0.01;
            else this.pulseBase = 1;
        }

        // Draw particles
        if (!this.isMobile) {
            this.ctx.shadowBlur = this.isPlaying ? 15 : 0;
            this.ctx.shadowColor = 'rgba(149, 0, 255, 0.5)';
        }

        this.particles.forEach((p, i) => {
            // Speed multiplier: fast when playing, slow when paused
            const speedMult = this.isPlaying ? 5.0 : 1.0;
            
            p.x += p.baseSpeedX * speedMult;
            p.y += p.baseSpeedY * speedMult;

            // Wrap around screen
            if (p.x < 0) p.x = this.width;
            if (p.x > this.width) p.x = 0;
            if (p.y < 0) p.y = this.height;
            if (p.y > this.height) p.y = 0;

            // Draw
            this.ctx.beginPath();
            const size = p.size * (this.isPlaying ? this.pulseBase * 1.5 : 1);
            this.ctx.arc(p.x, p.y, size, 0, Math.PI * 2);
            
            // Color shifts when playing
            if (this.isPlaying) {
                this.ctx.fillStyle = `rgba(149, 0, 255, ${p.alpha + 0.2})`;
            } else {
                this.ctx.fillStyle = `rgba(255, 255, 255, ${p.alpha})`;
            }
            this.ctx.fill();
            
            // Draw connecting lines if close (web effect) when playing (PCs ONLY)
            if (this.isPlaying && !this.isMobile && i % 2 === 0) {
                for (let j = i + 1; j < i + 5 && j < this.particles.length; j++) {
                    const p2 = this.particles[j];
                    const dx = p.x - p2.x;
                    const dy = p.y - p2.y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    
                    if (dist < 100) {
                        this.ctx.beginPath();
                        this.ctx.strokeStyle = `rgba(149, 0, 255, ${0.2 * (1 - dist / 100)})`;
                        this.ctx.lineWidth = 0.5;
                        this.ctx.moveTo(p.x, p.y);
                        this.ctx.lineTo(p2.x, p2.y);
                        this.ctx.stroke();
                    }
                }
            }
        });

        if (!this.isMobile) this.ctx.shadowBlur = 0;

        // Center Pulse Circle (Visual Beat)
        if (this.isPlaying) {
            this.ctx.beginPath();
            this.ctx.arc(this.width / 2, this.height / 2, 300 * (this.pulseBase - 0.9), 0, Math.PI * 2);
            this.ctx.fillStyle = `rgba(149, 0, 255, 0.05)`;
            this.ctx.fill();
            
            this.ctx.beginPath();
            this.ctx.arc(this.width / 2, this.height / 2, 150 * (this.pulseBase - 0.95), 0, Math.PI * 2);
            this.ctx.strokeStyle = `rgba(149, 0, 255, 0.2)`;
            this.ctx.stroke();
        }

        requestAnimationFrame(() => this.animate());
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.animate();
    }

    stop() {
        this.running = false;
    }
}

// Global instance
let bgEffect;

function initEffects(canvasId) {
    if (bgEffect) bgEffect.stop();
    bgEffect = new ReactiveParticles(canvasId);
    bgEffect.start();
}

function setMusicState(isPlaying) {
    if (bgEffect) bgEffect.setPlaying(isPlaying);
}

function stopEffects() {
    if (bgEffect) bgEffect.stop();
}

/* --- Glitch Text Trigger --- */
function triggerGlitch(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;
    el.classList.remove('glitch-active');
    void el.offsetWidth; // Trigger reflow
    el.classList.add('glitch-active');
}
