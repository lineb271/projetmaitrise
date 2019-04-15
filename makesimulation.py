import matplotlib.pyplot as plt
import numpy as np
from progress.bar import Bar

import network
import simulation

world = network.World.load('simple-net.yml')
sim = simulation.Simulation.load('config.yml')


def run(world, simulationParameters):

    np.random.seed(simulationParameters.seed)
    # world.connectAlignments()
    for ui in world.userInputs:
        # link to alignment
        for al in world.alignments:
            al.points.computeCumulativeDistances()
            if al.idx == ui.alignmentIdx:
                ui.alignment = al
        ui.initDistributions()
        ui.generateHeadways(simulationParameters.duration)

    # suggestion, a voir si c'est le plus pratique
    for al in world.alignments:
        al.vehicles = []

    world.connectAlignments()

    userNum = 0

    bar = Bar('Processing')
    for i in range(int(np.floor(simulationParameters.duration/simulationParameters.timeStep))):
        # print('simulation step {}'.format(i))
        userNum = world.initUsers(i, simulationParameters.timeStep, userNum)

        for al in world.alignments:
            if al.vehicles is not None:
                for v in al.vehicles:
                    # world.defineLeader(v, i, sim.timeStep) # ligne a decommenter si l'on veut effectuer les calculs avec la fonction de recherche de leader
                    v.updateCurvilinearPositions(method="newell",
                                                 instant=i,
                                                 timeStep=simulationParameters.timeStep,
                                                 _nextAlignmentIdx=world.getNextAlignment(v, i, simulationParameters.timeStep),
                                                 occupiedAlignmentLength=world.occupiedAlignmentLength(v),
                                                 previouslyOccupiedAlignmentsLength=world.getPreviouslyOccupiedAlignmentsLength(v))
                    # network.World.replaceUSerOnTravelledAlignments(world, v)
            bar.next()
    #
    # for al in [world.getAlignmentById(0)]:
    #     for v in al.vehicles:
    #         world.moveUserToAlignment(v)


    # display
    plt.figure()
    for al in [world.getAlignmentById(0)]:
        for v in al.vehicles:
            if v.timeInterval is not None:
                v.plotCurvilinearPositions()
    plt.xlabel('time(s/100)')
    plt.ylabel('longitudinal coordinate (m)')
    plt.show()

    return world
