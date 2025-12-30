# 🚀 GitHub Pages Setup Guide

Your Bookshelf KBE Configurator demo is ready to be deployed to GitHub Pages!

## 📋 Steps to Enable GitHub Pages

### 1. Go to Repository Settings

Navigate to: `https://github.com/vebjornhegrand/BookshelfKBE/settings/pages`

Or manually:
1. Go to your repository: `https://github.com/vebjornhegrand/BookshelfKBE`
2. Click **Settings** tab
3. Click **Pages** in the left sidebar

### 2. Configure GitHub Pages

In the **Build and deployment** section:

- **Source**: Select `Deploy from a branch`
- **Branch**: Select `main`
- **Folder**: Select `/docs`
- Click **Save**

### 3. Wait for Deployment

GitHub will automatically build and deploy your site. This usually takes 1-2 minutes.

You'll see a message: "Your site is live at `https://vebjornhegrand.github.io/BookshelfKBE/`"

### 4. Access Your Live Demo

Once deployed, your demo will be available at:

**🌐 https://vebjornhegrand.github.io/BookshelfKBE/**

## ✅ What's Included in the Demo

The GitHub Pages demo includes:

- ✨ **Interactive UI** - Full bookshelf configurator interface
- 🧬 **Client-side GA** - JavaScript implementation of Genetic Algorithm
- 📊 **Cost Calculator** - Real-time cost estimation
- 🎨 **3D Visualization** - Three.js-based 3D viewer
- 📈 **GA Performance Charts** - Convergence visualization
- 📱 **Responsive Design** - Works on mobile and desktop

## 🔗 Adding to Your Portfolio

### Link Format
```markdown
[Bookshelf KBE Configurator](https://vebjornhegrand.github.io/BookshelfKBE/)
```

### Portfolio Description
```
An intelligent bookshelf design system combining Knowledge-Based Engineering (KBE), 
Genetic Algorithms, and 3D CAD visualization. Features semantic knowledge base 
(RDF/SPARQL), GA optimization, component reuse, and automated manufacturing analysis.

Technologies: Python, Flask, Apache Jena Fuseki, FreeCAD, Three.js, Genetic Algorithms
```

### Showcase Features
- **Knowledge-Based Engineering** - RDF triplestore with SPARQL queries
- **AI Optimization** - Multi-objective genetic algorithm
- **CAD Integration** - Parametric design with FreeCAD
- **Real-time 3D** - Interactive Three.js visualization
- **Full-stack** - Python backend + JavaScript frontend

## 🎯 Differences: Demo vs Full Application

### GitHub Pages Demo (Client-side)
- ✅ GA optimization in browser
- ✅ 3D visualization
- ✅ Cost calculation
- ✅ No server required
- ❌ No persistent Knowledge Base
- ❌ No FreeCAD CAD export
- ❌ No component inventory

### Full Application (Python Backend)
- ✅ All demo features
- ✅ Apache Jena Fuseki Knowledge Base
- ✅ FreeCAD CAD generation & export
- ✅ Component inventory management
- ✅ Order tracking
- ✅ Design reuse & popularity metrics
- ⚠️ Requires local setup or hosting

## 📝 Custom Domain (Optional)

If you have a custom domain, edit `docs/CNAME`:

```
bookshelf.yourdomain.com
```

Then configure DNS:
- Type: `CNAME`
- Name: `bookshelf` (or your subdomain)
- Value: `vebjornhegrand.github.io`

## 🐛 Troubleshooting

### Site Not Loading?
1. Wait 2-3 minutes after enabling Pages
2. Check Settings → Pages for deployment status
3. Ensure `/docs` folder is selected
4. Hard refresh: `Ctrl+Shift+R` (Windows) or `Cmd+Shift+R` (Mac)

### 3D Viewer Not Working?
- Ensure browser supports WebGL
- Check browser console for errors
- Try in a different browser (Chrome recommended)

### Changes Not Showing?
- Clear browser cache
- Wait for GitHub Pages rebuild (2-3 minutes)
- Check git push was successful

## 📚 Additional Resources

- [GitHub Pages Documentation](https://docs.github.com/en/pages)
- [Three.js Documentation](https://threejs.org/docs/)
- [RDF/SPARQL Tutorial](https://www.w3.org/TR/sparql11-query/)

---

**✨ Your Bookshelf KBE demo is now ready to showcase in your portfolio!**

