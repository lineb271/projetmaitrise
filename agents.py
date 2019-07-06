import networkx as nx
import numpy as np
from trafficintelligence import moving


class NewellMovingObject(moving.MovingObject):
    def __init__(self, num=None, timeInterval=None, positions=None, velocities=None, geometry=None,
                 userType=moving.userType2Num['unknown'], nObjects=None, initCurvilinear=False, desiredSpeed=None,
                 tau=None, d=None, criticalGap=None, initialCumulatedHeadway=None,
                 initialAlignment=None, amberProbability=None):
        super().__init__(num, timeInterval, positions, velocities, geometry, userType, nObjects, initCurvilinear)
        self.desiredSpeed = desiredSpeed
        self.tau = tau
        self.d = max(d, geometry)
        self.leader = None
        # other attributes necessary for computation
        self.initialCumulatedHeadway = initialCumulatedHeadway
        self.alignments = [initialAlignment]
        self.instantAtS0 = None  # time at which the vehicle's position is s=0 on the alignment
        self.arrivalInstantAtControlDevice = None
        self.criticalGap = criticalGap
        self.comingUser = None
        self.amberProbability = amberProbability

    def orderUsersByFirstInstant(self, other):
        # todo : modifier byPosition
        if self.getFirstInstant() > other.getFirstInstant():
            return other, self
        else:
            return self, other

    def getCriticalGap(self):
        return self.criticalGap

    def getInitialAlignment(self):
        '''Returns the user initial alignment '''
        return self.alignments[0]

    def getCurrentAlignment(self):
        '''Returns the user current alignment '''
        return self.alignments[-1]

    def addVisitedAlignment(self, al):
        if al != self.getCurrentAlignment():  # allow to visit alignment again
            self.alignments.append(al)

    def setArrivalInstantAtControlDevice(self, instant):
        # it could be interesting to store the cd at which the user stops
        if self.arrivalInstantAtControlDevice is None:
            self.arrivalInstantAtControlDevice = instant

    def resetArrivalInstantAtControlDevice(self):
        self.arrivalInstantAtControlDevice = None

    def getWaitingTimeAtControlDevice(self, instant):
        return instant-self.arrivalInstantAtControlDevice
        
    def getDistanceFromOriginAt(self, idx, world):
        G = world.graph
        G.add_node(self)
        s = self.getCurvilinearPositionAt(idx)
        upstreamDistance = s[0]
        downstreamDistance = self.getCurrentAlignment().getTotalDistance() - upstreamDistance

        entryNode = world.alignments[s[2]].getEntryNode()
        exitNode = world.alignments[s[2]].getExitNode()

        G.add_weighted_edges_from([(entryNode, self, upstreamDistance)])
        G.add_weighted_edges_from([(self, exitNode, downstreamDistance)])
        distance = nx.shortest_path_length(G, source=self.getInitialAlignment().getEntryNode(), target=self, weight='weight')
        G.remove_node(self)
        return [distance, s[1], s[2]]

    def getLeaderGeometry(self):
        return self.leader.geometry

    def getDistanceFromOriginAtInstant(self, instant, world):
        return self.getDistanceFromOriginAt(instant - self.getFirstInstant(), world)

    def interpolateCurvilinearPositions(self, t):
        '''Linear interpolation of curvilinear positions, t being a float

        relies on list of visited alignments'''
        i = int(np.floor(t))
        p1 = self.getCurvilinearPositionAtInstant(i)
        p2 = self.getCurvilinearPositionAtInstant(i + 1)
        alpha = t - float(i)
        if p1[2] == p2[2]:
            return [(1 - alpha) * p1[0] + alpha * p2[0], (1 - alpha) * p1[1] + alpha * p2[1], p1[2]]
        else:
            # compute coord of p2 wrt alignment of p1
            i = 0
            while self.alignments[i].idx != p1[2]:
                i += 1
            i1 = i
            s2 = self.alignments[i1].getTotalDistance()
            i += 1
            while self.alignments[i].idx != p2[2]:
                s2 += self.alignments[i].getTotalDistance()
                i += 1
            s2 += p2[0]
            interS = (1 - alpha) * p1[0] + alpha * s2
            # find alignment of interpolated position
            i = i1
            while interS > self.alignments[i].getTotalDistance():
                interS -= self.alignments[i].getTotalDistance()
                i += 1
            return [interS, (1 - alpha) * p1[1] + alpha * p2[1], i]
        # if hasattr(self, 'curvilinearPositions') and if self.existsAtInstant(t):
        #     i = int(floor(t))
        #     p1 = self.getCurvilinearPositionAtInstant(i)
        #     p2 = self.getCurvilinearPositionAtInstant(i+1)
        #     if p1[2] != p2[2] and alignments is not None:
        #         al, s = alignments[p1[2]].getNextAlignment((1-alpha)*p1[0]+alpha*p2[0]) # it works if no possible bifurcation at end of alignment
        #         return [s, (1-alpha)*p1[1]+alpha*p2[1], al[-1].idx]
        # return super().interpolateCurvilinearPositions(t, alignments)

    def getTravelledDistance(self, alignmentIdx1, alignmentIdx2):
        '''Returns travelled distance from alignmentIdx1 to beginning of alignmentIdx2 '''
        if alignmentIdx1 == alignmentIdx2:
            return 0.
        else:
            i = 0
            while self.alignments[i].idx != alignmentIdx1:
                i += 1
            s = self.alignments[i].getTotalDistance()
            while self.alignments[i].idx == alignmentIdx2:
                s += self.alignments[i].getTotalDistance()
                i += 1
            return s

    def updateCurvilinearPositions(self, instant, timeStep, world, maxSpeed=None, acceleration=None):
        '''Update curvilinear position of user at new instant'''
        # TODO reflechir pour des control devices
        if self.curvilinearPositions is None:  # vehicle without positions
            if self.instantAtS0 is None:
                if self.leader is None:
                    self.instantAtS0 = self.initialCumulatedHeadway
                elif self.leader.curvilinearPositions is not None and self.leader.curvilinearPositions.getSCoordAt(-1) > self.d and len(self.leader.curvilinearPositions) >= 2:
                    firstInstantAfterD = self.leader.getLastInstant()
                    while self.leader.existsAtInstant(firstInstantAfterD) and self.leader.getCurvilinearPositionAtInstant(firstInstantAfterD - 1)[0] > self.d: # find first instant after d
                        firstInstantAfterD -= 1  # if not recorded position before self.d, we extrapolate linearly from first known position
                    leaderSpeed = self.leader.getCurvilinearVelocityAtInstant(firstInstantAfterD-1)[0]
                    self.instantAtS0 = self.tau + firstInstantAfterD*timeStep - (self.leader.getCurvilinearPositionAtInstant(firstInstantAfterD)[0] - self.d) * timeStep / leaderSpeed  # second part is the time at which leader is at self.d
                    if self.instantAtS0 < self.initialCumulatedHeadway:  # obj appears at instant initialCumulatedHeadway at x=0 with desiredSpeed
                        self.instantAtS0 = self.initialCumulatedHeadway
            elif instant*timeStep > self.instantAtS0:
                # firstInstant = int(ceil(self.instantAtS0/timeStep))# this first instant is instant by definition
                leaderInstant = instant - self.tau / timeStep
                if self.leader is None:
                    s = (timeStep*instant-self.instantAtS0)*self.desiredSpeed
                    self.timeInterval = moving.TimeInterval(instant, instant)
                    self.curvilinearPositions = moving.CurvilinearTrajectory([s], [0.], [self.getInitialAlignment().idx])
                    self.curvilinearVelocities = moving.CurvilinearTrajectory()
                    try:
                        world.alignments[self.getInitialAlignment().idx].currentUsers[instant].append(self.num)
                    except:
                        world.alignments[self.getInitialAlignment().idx].currentUsers[instant] = [self.num]
                elif self.leader.existsAtInstant(leaderInstant):
                    self.timeInterval = moving.TimeInterval(instant, instant)
                    freeFlowCoord = (instant*timeStep-self.instantAtS0)*self.desiredSpeed
                    # constrainedCoord at instant = xn-1(t = instant*timeStep-self.tau)-self.d
                    constrainedCoord = self.leader.interpolateCurvilinearPositions(leaderInstant)[0] - self.d
                    self.curvilinearPositions = moving.CurvilinearTrajectory([min(freeFlowCoord, constrainedCoord)], [0.], [self.getInitialAlignment().idx])
                    self.curvilinearVelocities = moving.CurvilinearTrajectory()
                    try:
                        world.alignments[self.getInitialAlignment().idx].currentUsers[instant].append(self.num)
                    except:
                        world.alignments[self.getInitialAlignment().idx].currentUsers[instant] = [self.num]

        else:
            s1 = self.curvilinearPositions.getSCoordAt(-1)
            freeFlowCoord = s1 + self.desiredSpeed * timeStep
            if self.leader is None:
                s2 = freeFlowCoord
            else:
                if self.leader.existsAtInstant(instant):
                    # compute leader coordinate with respect to current alignment
                    p = self.leader.interpolateCurvilinearPositions(instant - self.tau / timeStep)
                    constrainedCoord = p[0] + self.leader.getTravelledDistance(self.curvilinearPositions.getLaneAt(-1), p[2]) - self.d
                else:  # simplest is to continue at constant speed
                    ds = self.curvilinearVelocities.getSCoordAt(-1)
                    constrainedCoord = s1 + ds
                s2 = min(freeFlowCoord, constrainedCoord)
            nextAlignments, s2onNextAlignment = self.getCurrentAlignment().getNextAlignment(nextS=s2, user=self, instant=instant, world=world, timeStep=timeStep)
            if nextAlignments is not None:
                self.curvilinearPositions.addPositionSYL(s2onNextAlignment, 0., nextAlignments[-1].idx)
                for al in nextAlignments[1:]:
                    self.addVisitedAlignment(al)
                if self.curvilinearPositions.getLaneAt(-2) == self.curvilinearPositions.getLaneAt(-1):
                    laneChange = None
                else:
                    laneChange = (self.curvilinearPositions.getLaneAt(-2), self.curvilinearPositions.getLaneAt(-1))
                self.curvilinearVelocities.addPositionSYL(s2 - s1, 0., laneChange)
                self.setLastInstant(instant)
                # TODO test if the new alignment is different from leader, update leader
                try:
                    world.alignments[nextAlignments[-1].idx].currentUsers[instant].append(self.num)
                except:
                    world.alignments[nextAlignments[-1].idx].currentUsers[instant] = [self.num]

            else:
                world.newlyCompleted.append(self)
