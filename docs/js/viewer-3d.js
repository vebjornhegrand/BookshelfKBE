// viewer-3d.js - Three.js 3D visualization for bookshelf designs

class BookshelfViewer {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;
        this.bookshelf = null;
        this.wireframeMode = false;
        
        this.init();
    }
    
    init() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1a1f2e);
        
        // Camera
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(45, aspect, 10, 10000);
        this.camera.position.set(2000, 1200, 2000);
        this.camera.lookAt(0, 0, 0);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.shadowMap.enabled = true;
        this.container.appendChild(this.renderer.domElement);
        
        // Controls
        this.controls = new THREE.OrbitControls(this.camera, this.renderer.domElement);
        this.controls.enableDamping = true;
        this.controls.dampingFactor = 0.05;
        
        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);
        
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(1000, 2000, 1000);
        directionalLight.castShadow = true;
        this.scene.add(directionalLight);
        
        const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.3);
        directionalLight2.position.set(-1000, 500, -500);
        this.scene.add(directionalLight2);
        
        // Grid helper
        const gridHelper = new THREE.GridHelper(3000, 30, 0x444444, 0x222222);
        this.scene.add(gridHelper);
        
        // Axes helper (optional)
        const axesHelper = new THREE.AxesHelper(500);
        this.scene.add(axesHelper);
        
        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
        
        // Start animation loop
        this.animate();
    }
    
    generateBookshelf(design) {
        // Remove old bookshelf
        if (this.bookshelf) {
            this.scene.remove(this.bookshelf);
        }
        
        this.bookshelf = new THREE.Group();
        
        const { width, height, depth, thickness, add_top, shelves, dividers } = design;
        
        // Material for panels
        const woodMaterial = new THREE.MeshStandardMaterial({
            color: 0xd4a574,
            roughness: 0.7,
            metalness: 0.1
        });
        
        const edgeMaterial = new THREE.MeshStandardMaterial({
            color: 0x8b6f47,
            roughness: 0.8,
            metalness: 0.0
        });
        
        // Helper function to create a panel
        const createPanel = (w, h, d, x, y, z) => {
            const geometry = new THREE.BoxGeometry(w, h, d);
            const mesh = new THREE.Mesh(geometry, woodMaterial);
            mesh.position.set(x, y, z);
            mesh.castShadow = true;
            mesh.receiveShadow = true;
            
            // Add edge lines for definition
            const edges = new THREE.EdgesGeometry(geometry);
            const line = new THREE.LineSegments(edges, 
                new THREE.LineBasicMaterial({ color: 0x000000, opacity: 0.3, transparent: true }));
            mesh.add(line);
            
            return mesh;
        };
        
        // Side panels (vertical)
        const leftPanel = createPanel(thickness, height, depth, -width/2 + thickness/2, height/2, 0);
        this.bookshelf.add(leftPanel);
        
        const rightPanel = createPanel(thickness, height, depth, width/2 - thickness/2, height/2, 0);
        this.bookshelf.add(rightPanel);
        
        // Bottom panel (horizontal)
        const bottomPanel = createPanel(width, thickness, depth, 0, thickness/2, 0);
        this.bookshelf.add(bottomPanel);
        
        // Top panel (optional)
        if (add_top) {
            const topPanel = createPanel(width, thickness, depth, 0, height - thickness/2, 0);
            this.bookshelf.add(topPanel);
        }
        
        // Shelves
        shelves.forEach(shelfY => {
            const shelf = createPanel(width - thickness * 2, thickness, depth, 0, shelfY, 0);
            this.bookshelf.add(shelf);
        });
        
        // Dividers
        dividers.forEach(dividerX => {
            const divider = createPanel(thickness, height, depth, dividerX - width/2, height/2, 0);
            this.bookshelf.add(divider);
        });
        
        this.scene.add(this.bookshelf);
        
        // Center camera on bookshelf
        this.resetView();
    }
    
    resetView() {
        if (this.bookshelf) {
            const box = new THREE.Box3().setFromObject(this.bookshelf);
            const center = box.getCenter(new THREE.Vector3());
            const size = box.getSize(new THREE.Vector3());
            
            const maxDim = Math.max(size.x, size.y, size.z);
            const fov = this.camera.fov * (Math.PI / 180);
            let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
            cameraZ *= 1.5; // Add some padding
            
            this.camera.position.set(cameraZ, cameraZ * 0.6, cameraZ);
            this.camera.lookAt(center);
            this.controls.target.copy(center);
        }
    }
    
    toggleWireframe() {
        this.wireframeMode = !this.wireframeMode;
        
        if (this.bookshelf) {
            this.bookshelf.traverse((child) => {
                if (child instanceof THREE.Mesh) {
                    child.material.wireframe = this.wireframeMode;
                }
            });
        }
    }
    
    exportSTL() {
        alert('STL export is available in the full Python version with FreeCAD integration.\n\n' +
              'This demo uses Three.js for visualization only.\n\n' +
              'See the GitHub repository for the complete implementation.');
    }
    
    onWindowResize() {
        if (!this.container) return;
        
        const width = this.container.clientWidth;
        const height = this.container.clientHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(width, height);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        if (this.controls) {
            this.controls.update();
        }
        
        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }
}

