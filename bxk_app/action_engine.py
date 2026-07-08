class ActionEngine:

    def evaluate(self, quality):

        score = quality["score"]

        if score >= 90:

            action = "ENTER"

        elif score >= 80:

            action = "WAIT"

        elif score >= 70:

            action = "MONITOR"

        else:

            action = "NO TRADE"

        return {

            "action": action

        }