# Assessment manual

Faculty open Manage course content, add a quiz, then add questions while unpublished. Choose multiple choice, true/false, short answer, fill in the blank, matching or essay. Set positive point weights. Multiple choice requires four options and a correct letter. True/false uses `[true]` or `[false]`; short/blank uses a JSON list of accepted answers; matching uses a JSON object of prompt/value pairs. Essay answers require manual grading. Short answers ignore case and whitespace; matching receives proportional credit.

Assessment policy sets the timer, random order, number of questions selected from the quiz pool, allowed attempts and highest/latest/average percentage aggregation. A selection of zero uses every question. Policies and questions lock when a session begins. Each retake selects its own pool once, retained across reloads. Instructor question banks copy independent questions into a quiz. Configure accommodations before sessions begin.

Use Grade attempts to score essays or correct automatically scored responses. Every response requires a score in its possible range before the attempt is graded. Old attempts created before response storage remain intact and cannot be regraded through this screen. Generic admin assessment records are read-only; use the course authoring and grading workflows.

Edit the quiz to control Results released. Withheld results and attempts awaiting manual grading do not expose scores in the student portal. Released graded attempts contribute normalized percentages under the chosen aggregation rule. This assessment percentage does not automatically replace registrar final grades or the assignment-only weighted gradebook. Proctoring integration remains outstanding.
