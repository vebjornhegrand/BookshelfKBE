# 🔧 Bookshelf KBE Configurator

An intelligent bookshelf design system combining **Knowledge-Based Engineering (KBE)**, **Genetic Algorithms (GA)**, and **3D CAD visualization** to automate furniture configuration and manufacturing.

[![Live Demo](https://img.shields.io/badge/demo-live-success)](https://vebjornhegrand.github.io/BookshelfKBE/)
[![Python](https://img.shields.io/badge/python-3.9+-blue)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/flask-2.0+-green)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## 🎯 Project Overview

This project demonstrates a complete **Knowledge-Based Engineering** system for furniture design and manufacturing. It showcases:

- **Semantic Knowledge Base** using Apache Jena Fuseki (RDF/SPARQL)
- **Genetic Algorithm optimization** for design generation
- **Component reuse & inventory management**
- **Automated CAD generation** with FreeCAD
- **Real-time 3D visualization** using Three.js
- **Cost & manufacturability analysis**

### 🌐 Try It Live

**[Live Demo on GitHub Pages](https://vebjornhegrand.github.io/BookshelfKBE/)** *(Client-side demo version)*

The live demo runs entirely in your browser with JavaScript-based GA optimization and Three.js visualization. For the full backend features (Knowledge Base, FreeCAD CAD export), see installation instructions below.

---

## ✨ Key Features

### 1. **Knowledge-Based Engineering (KBE)**
- **RDF Ontology** for bookshelf designs, components, and orders
- **SPARQL queries** for semantic search and reasoning
- **Design reuse** - Find similar existing designs before creating new ones
- **Component inventory** - Track and reuse manufactured panels
- **Order tracking** with popularity metrics

### 2. **Genetic Algorithm Optimization**
- Multi-objective optimization (cost, strength, manufacturability)
- Population-based evolutionary search
- KB-seeded initialization for faster convergence
- Constraint satisfaction (customer dimensions, load requirements)

### 3. **3D CAD Integration**
- **FreeCAD** scripting for parametric design
- Automated joint generation (cam-locks, dowels, shelf pins)
- STL/STEP export for manufacturing
- Three.js web visualization

### 4. **Cost & Manufacturing Analysis**
- Material cost calculation
- Joint & hardware costing
- Assembly time estimation
- Manufacturability scoring
- Load capacity analysis

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Web Interface (Flask)                   │
│  - Design configurator  - 3D viewer  - Cost analysis        │
└───────────────┬─────────────────────────────────────────────┘
                │
    ┌───────────┼───────────┬─────────────┬──────────────┐
    │           │           │             │              │
┌───▼────┐ ┌───▼────┐ ┌───▼─────┐ ┌────▼─────┐ ┌──────▼───────┐
│   KB   │ │   GA   │ │ FreeCAD │ │  Costing │ │ Manufactur.  │
│ (Fuseki)│ │Optimizer│ │ Adapter │ │  Module  │ │   Analysis   │
└────────┘ └────────┘ └─────────┘ └──────────┘ └──────────────┘
     │
┌────▼─────────────────────────────────────────────────────────┐
│              RDF Knowledge Base (TDB2)                        │
│  - Bookshelf designs    - Components inventory               │
│  - Customer orders      - Material properties                │
└───────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation & Setup

### Prerequisites

- **Python 3.9+**
- **Java 11+** (for Fuseki)
- **FreeCAD** (optional, for full CAD features)

### 1. Clone the Repository

```bash
git clone https://github.com/vebjornhegrand/BookshelfKBE.git
cd BookshelfKBE
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 3. Setup Apache Jena Fuseki (Knowledge Base)

**Option A: Using the setup script (macOS/Linux)**
```bash
bash setup_fuseki.sh
```

**Option B: Manual setup**
```bash
# Download Fuseki
curl -O https://archive.apache.org/dist/jena/binaries/apache-jena-fuseki-5.2.0.tar.gz
tar -xzf apache-jena-fuseki-5.2.0.tar.gz

# Start Fuseki server
cd apache-jena-fuseki-5.2.0
./fuseki-server --port 3030
```

### 4. Run the Web Application

```bash
python web_app.py
```

Open your browser to: **http://localhost:5001**

---

## 📖 Usage

### Basic Workflow

1. **Specify Requirements**
   - Set dimensions (width, height, depth)
   - Choose material and joint type
   - Define load requirements

2. **Search Knowledge Base** (optional)
   - Find similar existing designs
   - Reuse components from inventory

3. **Optimize with GA**
   - Generate optimized design
   - View cost breakdown
   - See component allocation plan

4. **Visualize in 3D**
   - Inspect design geometry
   - View joints and holes
   - Export CAD files (STL/STEP)

5. **Place Order**
   - Record in knowledge base
   - Update component inventory
   - Track design popularity

### Example: Create a Custom Bookshelf

```python
from ga_optimizer import GeneticOptimizer, GAConfig
from model import build_model

# Define requirements
requirements = {
    'width': 800,
    'height': 1800,
    'depth': 300,
    'num_shelves': 4,
    'material': 'melamine_pb',
    'target_load': 50
}

# Optimize design
config = GAConfig(population_size=30, generations=15)
optimizer = GeneticOptimizer(config)
design = optimizer.optimize(requirements)

# Generate CAD
from fc_adapter import make_bookshelf, run_joints
bookshelf = make_bookshelf(design)
joints = run_joints(bookshelf)
```

---

## 📁 Project Structure

```
BookshelfKBE/
├── web_app.py              # Flask web application
├── kb_manager.py           # Fuseki KB interface
├── ga_optimizer.py         # Genetic algorithm implementation
├── model.py                # Bookshelf data model
├── fc_adapter.py           # FreeCAD integration
├── costing.py              # Cost calculation
├── manufacturability.py    # Manufacturing analysis
├── joints.py               # Joint generation logic
├── materials.py            # Material properties
├── rdf_schema.ttl          # RDF ontology definition
├── requirements.txt        # Python dependencies
├── setup_fuseki.sh         # Fuseki setup script
├── static/                 # CSS/JS assets
│   ├── css/style.css
│   └── js/
│       ├── app.js          # Main app logic
│       └── viewer.js       # 3D visualization
├── templates/
│   └── configurator.html   # Web interface
└── docs/                   # GitHub Pages demo
    ├── index.html
    └── js/
        ├── ga-optimizer.js
        ├── cost-calculator.js
        ├── viewer-3d.js
        └── app-demo.js
```

---

## 🧬 Genetic Algorithm Details

The GA optimizes bookshelf designs across multiple objectives:

### Fitness Function Components
1. **Cost Minimization** - Material, joints, assembly
2. **Structural Integrity** - Load capacity, thickness-to-height ratio
3. **Manufacturability** - Standard dimensions, material efficiency
4. **Aesthetic Quality** - Even shelf spacing, proportion

### GA Parameters
- **Population Size**: 30 individuals
- **Generations**: 15 iterations
- **Mutation Rate**: 0.30 (exploration)
- **Crossover Rate**: 0.80 (exploitation)
- **Selection**: Tournament selection (size 3)
- **Elitism**: Top 3 preserved

### KB-Seeded Initialization
When similar designs exist in the KB, they seed the initial population for faster convergence to known good solutions.

---

## 🗄️ Knowledge Base Schema

The RDF ontology defines:

```turtle
:BookshelfDesign
  :hasWidth (mm)
  :hasHeight (mm)
  :hasDepth (mm)
  :hasThickness (mm)
  :hasMaterial (string)
  :totalCost (USD)
  :maxLoad (kg)
  :popularityScore (int)
  :generatedBy ("KB_SEARCH" | "GA_OPTIMIZED" | "MANUAL")
  :hasComponent* (:Shelf | :Divider)
  :usesComponent* :Component

:Component
  :componentType ("side_panel" | "shelf_board" | "divider")
  :componentWidth/Height/Depth/Thickness (mm)
  :stockQuantity (int)
  :componentStatus ("available" | "reserved" | "pending_fabrication")

:Order
  :orderedBy :Customer
  :orderedDesign :BookshelfDesign
  :quantity (int)
  :orderDate (dateTime)
```

---

## 🎨 Technologies Used

### Backend
- **Python 3.9+** - Core logic
- **Flask 2.0** - Web framework
- **Apache Jena Fuseki** - RDF triplestore
- **SPARQL** - Semantic queries
- **FreeCAD** - CAD generation (Python API)
- **NumPy** - Numerical computations

### Frontend
- **HTML5/CSS3** - UI
- **JavaScript ES6** - Client logic
- **Three.js** - 3D visualization
- **Chart.js** - Data visualization

### Tools & Infrastructure
- **Git** - Version control
- **GitHub Pages** - Demo hosting
- **RDF/OWL** - Ontology modeling

---

## 📊 Performance Metrics

**Typical GA Optimization:**
- Generations: 15
- Evaluation time: ~2-3 seconds
- Convergence: 85% by generation 10

**KB Query Performance:**
- Design search: <50ms
- Component allocation: <100ms
- SPARQL complexity: O(log n) with indexing

**CAD Generation:**
- FreeCAD modeling: ~3-5 seconds
- Joint generation: ~1-2 seconds
- STL export: ~1 second

---

## 🔮 Future Enhancements

- [ ] Multi-material designs
- [ ] Machine learning for cost prediction
- [ ] AR visualization (mobile)
- [ ] Automated cutting list generation
- [ ] Integration with CNC machines
- [ ] Customer preference learning
- [ ] Sustainability metrics (CO₂, recyclability)

---

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional joint types
- More material options
- Enhanced manufacturability rules
- UI/UX improvements
- Performance optimization

---

## 📄 License

This project is licensed under the **MIT License** - see [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Vebjørn Hegrand**

- GitHub: [@vebjornhegrand](https://github.com/vebjornhegrand)
- Portfolio: [vebjornhegrand.github.io/BookshelfKBE](https://vebjornhegrand.github.io/BookshelfKBE)

---

## 📚 References & Inspiration

- **Knowledge-Based Engineering**: Techniques for capturing and reusing design knowledge
- **Genetic Algorithms**: John Holland's evolutionary optimization principles
- **Semantic Web**: W3C RDF/OWL standards for knowledge representation
- **Parametric Design**: FreeCAD's scripting capabilities for generative design

---

## 🙏 Acknowledgments

- Apache Jena project for the excellent Fuseki triplestore
- FreeCAD community for the powerful CAD engine
- Three.js contributors for 3D visualization tools

---

**⭐ If you find this project interesting, please star the repository!**

