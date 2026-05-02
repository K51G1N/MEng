from typing import Iterable
import numpy as np


def annonymous(pop_vector_a, pop_vector_b, vector_c, weight):
    output = weight * (pop_vector_a - pop_vector_b) + vector_c

def rosenbrock(a, b, x, y):
    return (a - x)**2 + b * (y - x**2)**2

def sum_of_squares(x: Iterable[float]) -> float:
    return sum(x_i**2 for x_i in x)

def objective_function(x):
    return 0

def differential_evolution(objective_function, bounds, population_size, generations):
    for i in range(iter)
        for j in range(population_size):
            # Mutation and crossover steps would go here
            pass


def main():
    bounds = np.asarray([(-5.0,5.0),(-5.0,5.0)])
    population = bounds[:, 0] + (np.random.rand(population_size, len(bounds)) * (bounds[:, 1] - bounds[:, 0]))
    differential_evolution(objective_function, bounds, population_size=20, generations=100)


if __name__ == "__main__":
    main()
