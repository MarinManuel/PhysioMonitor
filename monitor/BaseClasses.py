import wx


class Mouse(object):
    def __init__(self, weight=None, sex=None, strain="", genotype="", dob=None):
        self.weight = weight
        self.sex = sex
        self.strain = strain
        self.genotype = genotype
        self.dob = dob


class Experiment(object):
    def __init__(self, date=wx.DateTime(), comments="", prevDrugs=[],
                 prevMouseStrains=set(), prevMouseGenotypes=set(), mouse=Mouse()):
        self.date = date
        self.comments = comments
        self.prevDrugList = prevDrugs
        self.prevStrainList = prevMouseStrains
        self.prevGenotypeList = prevMouseGenotypes
        self.mouse = mouse

    def writeHeader(self):
        header = u'Exp Date: %s\n' % self.date.Format("%a %b %d %Y")
        header += "\n"
        header += "Mouse %s %s" % (self.mouse.strain, self.mouse.genotype)
        header += " %s" % self.mouse.sex
        header += "\n"
        header += "DoB:"
        if (self.mouse.dob is not None) and self.mouse.dob.IsValid():
            age = self.date - self.mouse.dob
            header += self.mouse.dob.Format(" %a %b %d %Y")
            header += " (%d days)" % age.GetDays()
        header += "\n"
        header += "Weight:"
        if self.mouse.weight > 0:
            header += " %dg" % self.mouse.weight
        header += "\n"
        header += "\n"
        header += "Drugs:\n"
        for drug in self.prevDrugList:
            header += drug.printForList()
            header += "\n"
        header += "\n"
        header += "Comments:\n"
        header += self.comments
        header += "\n"
        return header


class Drug(object):
    def __init__(self, name, dose):
        self.name = name
        self.dose = dose

    def printForList(self):
        return "%-12s| %4d uL" % (self.name, self.dose)
