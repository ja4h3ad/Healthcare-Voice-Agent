from datetime import datetime

class Insurance:
    def __init__(self, insuranceId, insuranceCompany, groupNumber, memberID, createdAt=None, updatedAt=None):
        self.insuranceId = str(insuranceId)
        self.insuranceCompany = str(insuranceCompany)
        self.groupNumber = str(groupNumber)
        self.memberID = str(memberID)

        if createdAt:
            self.createdAt = datetime.strptime(str(createdAt), "%Y-%m-%d %H:%M:%S")
        else:
            self.createdAt = datetime.now()

        if updatedAt:
            self.updatedAt = datetime.strptime(str(updatedAt), "%Y-%m-%d %H:%M:%S")
        else:
            self.updatedAt = datetime.now()
