# ga_optimizer.py - Clean and Stable Genetic Algorithm for Bookshelf Optimization
"""
Elegant GA optimizer that properly balances cost, strength, and manufacturability.
Key improvements:
- Material costs are properly included (solid wood costs more than plywood)
- Fitness rewards thinner panels for stronger materials (efficiency)
- Stable random seeding for repeatability
- Clean mutation and crossover strategies
"""

import random
import numpy as np
from typing import List, Dict, Any
from dataclasses import dataclass
import logging

from model import Model, Shelf, Divider
from costing import estimate
from manufacturability import analyze
from materials import (
    get_material,
    calculate_shelf_deflection,
    calculate_load_capacity,
    MaterialSpec
)

logger = logging.getLogger(__name__)

# Set random seeds for repeatability
random.seed(42)
np.random.seed(42)

# Engineering constraints
MIN_THICKNESS = 12.0              # Absolute minimum
PRACTICAL_MIN_THICKNESS = 16.0    # For reliable fasteners
MAX_THICKNESS = 32.0              # Practical maximum
SAFETY_FACTOR = 1.25              # 25% capacity margin


@dataclass
class GAConfig:
    """Configuration for genetic algorithm."""
    population_size: int = 40
    generations: int = 20
    mutation_rate: float = 0.15
    crossover_rate: float = 0.8
    elite_count: int = 3
    
    # Fitness weights (total = 1.0)
    cost_weight: float = 0.35
    structural_weight: float = 0.40
    efficiency_weight: float = 0.15
    manufacturability_weight: float = 0.10


class Individual:
    """Represents one bookshelf design candidate."""
    
    def __init__(self, width, height, depth, num_shelves, material, target_load):
        self.width = width
        self.height = height
        self.depth = depth
        self.num_shelves = num_shelves
        self.material = material
        self.target_load = target_load
        
        # Genes
        self.thickness = int(round(random.uniform(PRACTICAL_MIN_THICKNESS, MAX_THICKNESS)))
        max_dividers = min(6, int(width / 300))  # One divider per ~300mm span
        self.num_dividers = random.randint(0, max_dividers)
        
        # Evaluation results
        self.fitness = float('inf')
        self.cost = 0
        self.capacity = 0
        self.deflection = 0
        self.warnings_count = 0
    
    def evaluate(self, config: GAConfig):
        """
        Evaluate fitness: lower is better.
        Balances cost, structural safety, efficiency, and manufacturability.
        """
        # Build model geometry
        clear_width = self.width - 2 * self.thickness
        bay_width = clear_width / (self.num_dividers + 1)
        
        # Create shelves (evenly spaced)
        shelves = []
        if self.num_shelves > 0:
            available_height = self.height - 2 * self.thickness
            spacing = available_height / (self.num_shelves + 1)
            for i in range(self.num_shelves):
                shelves.append(Shelf(z=self.thickness + (i + 1) * spacing))
        
        # Create dividers
        dividers = []
        if self.num_dividers > 0:
            for i in range(self.num_dividers):
                x = self.thickness + (i + 1) * bay_width
                dividers.append(Divider(x_center=x))
        
        model = Model(
            W=self.width, D=self.depth, H=self.height, t=self.thickness,
            add_top=True, shelves=shelves, dividers=dividers
        )
        
        # Get material spec
        mat_spec = get_material(self.material)
        
        # Calculate cost (passing material to get accurate pricing)
        cost_data = estimate(model, material=mat_spec)
        self.cost = cost_data['cost']['total']
        
        # Calculate structural performance
        self.deflection = calculate_shelf_deflection(
            bay_width, self.depth, self.thickness,
            self.target_load, self.material
        )
        self.capacity = calculate_load_capacity(
            bay_width, self.depth, self.thickness, self.material
        )
        
        # Manufacturability check
        design_data = {
            'W': self.width, 'D': self.depth, 'H': self.height, 't': self.thickness,
            'add_top': True, 'n_shelves': self.num_shelves, 'n_dividers': self.num_dividers,
            'material': self.material, 'target_load_kg': self.target_load
        }
        warnings = analyze(design_data, cost_data)
        self.warnings_count = len(warnings)
        
        # === Fitness Components (all normalized to 0-1, lower is better) ===
        
        # 1. Cost score (normalize by material-specific range)
        # Different materials have different cost ranges
        material_cost_ranges = {
            'melamine_pb': (50, 150),
            'plywood': (80, 200),
            'mdf': (50, 140),
            'solid_wood': (120, 300)
        }
        cost_min, cost_max = material_cost_ranges.get(self.material, (50, 200))
        cost_score = (self.cost - cost_min) / (cost_max - cost_min)
        cost_score = max(0.0, min(1.0, cost_score))
        
        # 2. Structural safety score (heavy penalty for unsafe designs)
        required_capacity = self.target_load * SAFETY_FACTOR
        deflection_limit = bay_width * mat_spec.deflection_limit_ratio  # L/250
        
        capacity_ratio = self.capacity / required_capacity if required_capacity > 0 else 1.0
        deflection_ratio = self.deflection / deflection_limit if deflection_limit > 0 else 0.0
        
        # Heavy penalties for violations
        capacity_penalty = max(0.0, 1.0 - capacity_ratio) * 2.0  # Double penalty
        deflection_penalty = max(0.0, deflection_ratio - 1.0)
        fastener_penalty = max(0.0, (PRACTICAL_MIN_THICKNESS - self.thickness) / 10.0)
        
        structural_score = min(1.0, capacity_penalty + deflection_penalty + fastener_penalty)
        
        # 3. Efficiency score (reward using material effectively, not over-engineering)
        # For safe designs, reward thinner panels (less material waste)
        if capacity_ratio >= 1.0 and deflection_ratio <= 1.0:
            # Safe design - reward thinness
            thickness_efficiency = (self.thickness - PRACTICAL_MIN_THICKNESS) / (MAX_THICKNESS - PRACTICAL_MIN_THICKNESS)
            over_engineering_penalty = max(0.0, (capacity_ratio - 1.5) / 2.0)  # Penalty for >150% overcapacity
            efficiency_score = thickness_efficiency * 0.7 + over_engineering_penalty * 0.3
        else:
            # Unsafe design - no efficiency reward
            efficiency_score = 1.0
        
        # 4. Manufacturability score
        mfg_score = min(1.0, self.warnings_count / 8.0)
        
        # Combined fitness (weighted sum)
        self.fitness = (
            config.cost_weight * cost_score +
            config.structural_weight * structural_score +
            config.efficiency_weight * efficiency_score +
            config.manufacturability_weight * mfg_score
        )
        
        return self.fitness
    
    def crossover(self, other):
        """Blend crossover for continuous genes, uniform for discrete genes."""
        child1 = Individual(
            self.width, self.height, self.depth, self.num_shelves,
            self.material, self.target_load
        )
        child2 = Individual(
            self.width, self.height, self.depth, self.num_shelves,
            self.material, self.target_load
        )
        
        # Blend crossover for thickness (interpolate between parents)
        alpha = random.random()
        child1.thickness = int(round(alpha * self.thickness + (1 - alpha) * other.thickness))
        child2.thickness = int(round((1 - alpha) * self.thickness + alpha * other.thickness))
        
        # Uniform crossover for dividers
        if random.random() < 0.5:
            child1.num_dividers = self.num_dividers
            child2.num_dividers = other.num_dividers
        else:
            child1.num_dividers = other.num_dividers
            child2.num_dividers = self.num_dividers
        
        return child1, child2
    
    def mutate(self, rate):
        """Gaussian mutation for thickness, ±1 for dividers."""
        if random.random() < rate:
            # Gaussian mutation for thickness (σ = 2mm), rounded to integer
            self.thickness += random.gauss(0, 2.0)
            self.thickness = int(round(max(MIN_THICKNESS, min(MAX_THICKNESS, self.thickness))))
        
        if random.random() < rate:
            # ±1 mutation for dividers
            max_dividers = min(6, int(self.width / 300))
            delta = random.choice([-1, 1])
            self.num_dividers = max(0, min(max_dividers, self.num_dividers + delta))
    
    def to_dict(self):
        """Serialize for reporting."""
        return {
            'width': self.width,
            'height': self.height,
            'depth': self.depth,
            'thickness': self.thickness,
            'num_dividers': self.num_dividers,
            'n_shelves': self.num_shelves,
            'material': self.material,
            'cost': round(self.cost, 2),
            'fitness': round(self.fitness, 4),
            'capacity_kg': round(self.capacity, 1),
            'deflection_mm': round(self.deflection, 2),
            'warnings_count': self.warnings_count
        }
    
    def to_model(self):
        """Convert to Model object."""
        clear_width = self.width - 2 * self.thickness
        bay_width = clear_width / (self.num_dividers + 1)
        
        shelves = []
        if self.num_shelves > 0:
            available_height = self.height - 2 * self.thickness
            spacing = available_height / (self.num_shelves + 1)
            for i in range(self.num_shelves):
                shelves.append(Shelf(z=self.thickness + (i + 1) * spacing))
        
        dividers = []
        if self.num_dividers > 0:
            for i in range(self.num_dividers):
                x = self.thickness + (i + 1) * bay_width
                dividers.append(Divider(x_center=x))
        
        return Model(
            W=self.width, D=self.depth, H=self.height, t=self.thickness,
            add_top=True, shelves=shelves, dividers=dividers
        )


class GeneticOptimizer:
    """Genetic algorithm optimizer for bookshelf designs."""
    
    def __init__(self, config: GAConfig = None):
        self.config = config or GAConfig()
        self.population = []
        self.best = None
        self.initial_best = None
        self.history = []
    
    def optimize(self, requirements: Dict[str, Any], kb_seed_designs: List = None):
        """
        Run genetic algorithm optimization.
        
        Args:
            requirements: Design requirements (width, height, depth, etc.)
            kb_seed_designs: Optional seed designs from knowledge base
            
        Returns:
            Best Model found
        """
        # Extract requirements
        width = requirements.get('width', 800)
        height = requirements.get('height', 2000)
        depth = requirements.get('depth', 300)
        num_shelves = requirements.get('num_shelves', 4)
        material = requirements.get('material', 'melamine_pb')
        target_load = requirements.get('target_load', 50)
        
        logger.info(f"Starting GA: {width}×{height}×{depth}mm, {num_shelves} shelves, "
                   f"{material}, target load {target_load}kg")
        
        # Initialize population
        self.population = [
            Individual(width, height, depth, num_shelves, material, target_load)
            for _ in range(self.config.population_size)
        ]
        
        # Seed from knowledge base (top 20%)
        if kb_seed_designs:
            seed_count = min(len(kb_seed_designs), self.config.population_size // 5)
            for i, kb_design in enumerate(kb_seed_designs[:seed_count]):
                self.population[i].thickness = int(round(kb_design.get('thickness', 18)))
                self.population[i].num_dividers = kb_design.get('n_dividers', 0)
        
        # Evaluate initial population
        for ind in self.population:
            ind.evaluate(self.config)
        
        self.population.sort(key=lambda x: x.fitness)
        self.initial_best = self.population[0]
        self.best = self.initial_best
        
        logger.info(f"Initial best: fitness={self.initial_best.fitness:.4f}, "
                   f"cost=${self.initial_best.cost:.2f}, "
                   f"thickness={self.initial_best.thickness}mm")
        
        # Evolution
        for gen in range(self.config.generations):
            # Select parents and create offspring
            next_gen = []
            
            # Elitism - preserve best solutions
            next_gen.extend(self.population[:self.config.elite_count])
            
            # Generate offspring
            while len(next_gen) < self.config.population_size:
                # Tournament selection
                tournament_size = 3
                parent1 = min(random.sample(self.population, tournament_size), 
                            key=lambda x: x.fitness)
                parent2 = min(random.sample(self.population, tournament_size), 
                            key=lambda x: x.fitness)
                
                # Crossover
                if random.random() < self.config.crossover_rate:
                    child1, child2 = parent1.crossover(parent2)
                else:
                    # Clone parents
                    child1 = Individual(width, height, depth, num_shelves, material, target_load)
                    child1.thickness = parent1.thickness
                    child1.num_dividers = parent1.num_dividers
                    child2 = Individual(width, height, depth, num_shelves, material, target_load)
                    child2.thickness = parent2.thickness
                    child2.num_dividers = parent2.num_dividers
                
                # Mutation
                child1.mutate(self.config.mutation_rate)
                child2.mutate(self.config.mutation_rate)
                
                # Evaluate
                child1.evaluate(self.config)
                child2.evaluate(self.config)
                
                next_gen.extend([child1, child2])
            
            # Trim to population size and sort
            self.population = next_gen[:self.config.population_size]
            self.population.sort(key=lambda x: x.fitness)
            
            # Track best
            if self.population[0].fitness < self.best.fitness:
                self.best = self.population[0]
            
            # Calculate diversity (std dev of thickness)
            thickness_diversity = np.std([ind.thickness for ind in self.population])
            
            # Log progress
            avg_fitness = np.mean([ind.fitness for ind in self.population])
            logger.info(f"Gen {gen+1}/{self.config.generations}: "
                       f"best_fit={self.population[0].fitness:.4f}, "
                       f"avg_fit={avg_fitness:.4f}, "
                       f"best_cost=${self.population[0].cost:.2f}, "
                       f"diversity={thickness_diversity:.2f}mm")
            
            # Record history
            self.history.append({
                'generation': gen + 1,
                'best_fitness': round(self.population[0].fitness, 4),
                'avg_fitness': round(avg_fitness, 4),
                'best_cost': round(self.population[0].cost, 2),
                'best_thickness': self.population[0].thickness,
                'best_dividers': self.population[0].num_dividers,
                'best_capacity': round(self.population[0].capacity, 1),
                'diversity': round(thickness_diversity, 2)
            })
        
        logger.info(f"GA Complete: fitness {self.best.fitness:.4f} → "
                   f"${self.best.cost:.2f}, {self.best.thickness}mm, "
                   f"{self.best.num_dividers} dividers, {self.best.capacity:.1f}kg capacity")
        
        return self.best.to_model()
    
    def get_optimization_report(self):
        """Get detailed optimization report."""
        if not self.best:
            return {}
        
        return {
            'initial_best_design': self.initial_best.to_dict() if self.initial_best else {},
            'best_design': self.best.to_dict(),
            'improvement': {
                'fitness_delta': round(self.initial_best.fitness - self.best.fitness, 4),
                'cost_delta': round(self.initial_best.cost - self.best.cost, 2),
                'thickness_delta': round(self.initial_best.thickness - self.best.thickness, 1),
            },
            'evolution_history': self.history
        }
