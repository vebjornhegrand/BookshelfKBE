// ga-optimizer.js - Client-side Genetic Algorithm for bookshelf optimization
// Simplified version for demo purposes

class GeneticOptimizer {
    constructor(config = {}) {
        this.populationSize = config.populationSize || 20;
        this.generations = config.generations || 15;
        this.mutationRate = config.mutationRate || 0.25;
        this.crossoverRate = config.crossoverRate || 0.7;
        this.eliteCount = config.eliteCount || 2;
        
        this.generationHistory = [];
        this.bestSolution = null;
    }
    
    optimize(requirements) {
        // Initialize population with random designs
        let population = this.initializePopulation(requirements);
        
        for (let gen = 0; gen < this.generations; gen++) {
            // Evaluate fitness for each individual
            population.forEach(individual => {
                individual.fitness = this.evaluateFitness(individual, requirements);
            });
            
            // Sort by fitness (higher is better)
            population.sort((a, b) => b.fitness - a.fitness);
            
            // Track best solution
            if (!this.bestSolution || population[0].fitness > this.bestSolution.fitness) {
                this.bestSolution = JSON.parse(JSON.stringify(population[0]));
            }
            
            // Record generation stats
            this.generationHistory.push({
                generation: gen,
                best: population[0].fitness,
                average: population.reduce((sum, ind) => sum + ind.fitness, 0) / population.length,
                worst: population[population.length - 1].fitness
            });
            
            // Create next generation
            let newPopulation = [];
            
            // Elitism - keep best individuals
            for (let i = 0; i < this.eliteCount; i++) {
                newPopulation.push(JSON.parse(JSON.stringify(population[i])));
            }
            
            // Fill rest with offspring
            while (newPopulation.length < this.populationSize) {
                let parent1 = this.selectParent(population);
                let parent2 = this.selectParent(population);
                
                let offspring = this.crossover(parent1, parent2, requirements);
                offspring = this.mutate(offspring, requirements);
                
                newPopulation.push(offspring);
            }
            
            population = newPopulation;
        }
        
        return this.bestSolution;
    }
    
    initializePopulation(requirements) {
        let population = [];
        const { width, height, depth, num_shelves, add_top, material } = requirements;
        
        for (let i = 0; i < this.populationSize; i++) {
            // Randomize thickness within reasonable range
            let thickness = 16 + Math.floor(Math.random() * 3) * 2; // 16, 18, 20, 22mm
            
            // Generate random shelf positions
            let shelves = [];
            for (let s = 0; s < num_shelves; s++) {
                let pos = 200 + Math.random() * (height - 400);
                shelves.push(pos);
            }
            shelves.sort((a, b) => a - b);
            
            // Random dividers (0-2)
            let numDividers = Math.floor(Math.random() * 3);
            let dividers = [];
            for (let d = 0; d < numDividers; d++) {
                let pos = 100 + Math.random() * (width - 200);
                dividers.push(pos);
            }
            dividers.sort((a, b) => a - b);
            
            population.push({
                width, height, depth, thickness,
                add_top, material,
                shelves, dividers,
                fitness: 0
            });
        }
        
        return population;
    }
    
    evaluateFitness(individual, requirements) {
        let score = 100; // Base score
        
        // 1. Cost penalty (prefer cheaper designs)
        const cost = this.estimateCost(individual);
        score -= cost / 5; // Reduce score based on cost
        
        // 2. Structural integrity (prefer thicker panels for taller units)
        const heightToThickness = individual.height / individual.thickness;
        if (heightToThickness > 120) {
            score -= 20; // Penalty for thin panels on tall units
        } else if (heightToThickness < 80) {
            score += 10; // Bonus for sturdy construction
        }
        
        // 3. Shelf spacing (prefer even distribution)
        if (individual.shelves.length > 1) {
            let spacings = [];
            let prevPos = 0;
            individual.shelves.forEach(pos => {
                spacings.push(pos - prevPos);
                prevPos = pos;
            });
            spacings.push(individual.height - prevPos);
            
            const avgSpacing = spacings.reduce((a, b) => a + b) / spacings.length;
            const variance = spacings.reduce((sum, s) => sum + Math.pow(s - avgSpacing, 2), 0) / spacings.length;
            score -= Math.sqrt(variance) / 10; // Penalty for uneven spacing
        }
        
        // 4. Material efficiency (prefer standard dimensions)
        const area = (individual.width * individual.height + 
                      individual.width * individual.depth * (individual.shelves.length + 2)) / 1000000;
        if (area < 0.5) score -= 5; // Too small, inefficient
        if (area > 3.0) score -= 10; // Too large, wasteful
        
        // 5. Load capacity check
        const targetLoad = requirements.target_load || 50;
        const maxLoad = this.estimateLoadCapacity(individual);
        if (maxLoad < targetLoad) {
            score -= (targetLoad - maxLoad) * 2; // Heavy penalty for insufficient load capacity
        } else if (maxLoad > targetLoad * 1.5) {
            score -= 5; // Minor penalty for over-engineering
        }
        
        return Math.max(0, score);
    }
    
    estimateCost(individual) {
        // Simplified cost calculation
        const materialCosts = {
            'melamine_pb': 30,
            'plywood': 45,
            'mdf': 28,
            'solid_wood': 80
        };
        
        const matCost = materialCosts[individual.material] || 35;
        
        // Calculate panel areas (m²)
        const sidePanelArea = (individual.thickness * individual.height * 2) / 1000000;
        const topBottomArea = (individual.width * individual.depth * (individual.add_top ? 2 : 1)) / 1000000;
        const shelfArea = (individual.width * individual.depth * individual.shelves.length) / 1000000;
        const dividerArea = (individual.thickness * individual.height * individual.dividers.length) / 1000000;
        
        const totalArea = sidePanelArea + topBottomArea + shelfArea + dividerArea;
        const materialCost = totalArea * matCost;
        
        // Joint costs
        const numJoints = (individual.shelves.length + 2) * 4 + individual.dividers.length * 4;
        const jointCost = numJoints * 0.5;
        
        // Assembly & overhead
        const assemblyCost = 25;
        
        return materialCost + jointCost + assemblyCost;
    }
    
    estimateLoadCapacity(individual) {
        // Simplified load calculation (kg per bay)
        const thicknessFactor = individual.thickness / 18;
        const spanFactor = Math.max(0.5, 1 - (individual.width / 2000));
        const materialFactors = {
            'melamine_pb': 1.0,
            'plywood': 1.3,
            'mdf': 0.9,
            'solid_wood': 1.5
        };
        const matFactor = materialFactors[individual.material] || 1.0;
        
        return Math.floor(50 * thicknessFactor * spanFactor * matFactor);
    }
    
    selectParent(population) {
        // Tournament selection
        const tournamentSize = 3;
        let best = null;
        
        for (let i = 0; i < tournamentSize; i++) {
            const candidate = population[Math.floor(Math.random() * population.length)];
            if (!best || candidate.fitness > best.fitness) {
                best = candidate;
            }
        }
        
        return best;
    }
    
    crossover(parent1, parent2, requirements) {
        if (Math.random() > this.crossoverRate) {
            return JSON.parse(JSON.stringify(parent1));
        }
        
        // Single-point crossover on shelf positions
        const offspring = JSON.parse(JSON.stringify(parent1));
        
        if (Math.random() < 0.5) {
            offspring.shelves = JSON.parse(JSON.stringify(parent2.shelves));
        }
        if (Math.random() < 0.5) {
            offspring.dividers = JSON.parse(JSON.stringify(parent2.dividers));
        }
        if (Math.random() < 0.5) {
            offspring.thickness = parent2.thickness;
        }
        
        return offspring;
    }
    
    mutate(individual, requirements) {
        // Mutate shelf positions
        individual.shelves = individual.shelves.map(pos => {
            if (Math.random() < this.mutationRate) {
                return Math.max(100, Math.min(individual.height - 100, 
                    pos + (Math.random() - 0.5) * 200));
            }
            return pos;
        });
        
        // Mutate divider positions
        individual.dividers = individual.dividers.map(pos => {
            if (Math.random() < this.mutationRate) {
                return Math.max(50, Math.min(individual.width - 50, 
                    pos + (Math.random() - 0.5) * 100));
            }
            return pos;
        });
        
        // Mutate thickness
        if (Math.random() < this.mutationRate * 0.5) {
            const thicknesses = [16, 18, 20, 22];
            individual.thickness = thicknesses[Math.floor(Math.random() * thicknesses.length)];
        }
        
        return individual;
    }
    
    getReport() {
        return {
            generations: this.generations,
            population_size: this.populationSize,
            best_fitness: this.bestSolution ? this.bestSolution.fitness : 0,
            convergence_history: this.generationHistory
        };
    }
}

