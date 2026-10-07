"""Generate a fixed, seeded task set with programmatically computed ground truth.

Output: suite/tasks.json  (list of task dicts)
Each task: {id, cat, prompt, grader, answer?, tests?, meta?}
"""
import itertools, json, math, random, datetime, os
from fractions import Fraction

R = random.Random(20261005)
T = []

ANS = "\n\nThink it through, then give the final answer on the last line in the form: ANSWER: <answer>"

def add(id, cat, prompt, grader, **kw):
    T.append(dict(id=id, cat=cat, prompt=prompt, grader=grader, **kw))

# ---------------------------------------------------------------- MATH (procedural)
# 1. lattice paths with blocked cells
for k in range(2):
    n = 8
    while True:
        blocked = set()
        while len(blocked) < 9:
            c = (R.randrange(n), R.randrange(n))
            if c not in [(0, 0), (n - 1, n - 1)]:
                blocked.add(c)
        dp = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if (i, j) in blocked: continue
                if i == 0 and j == 0: dp[i][j] = 1; continue
                dp[i][j] = (dp[i-1][j] if i else 0) + (dp[i][j-1] if j else 0)
        if dp[n-1][n-1] > 50: break
    bl = ", ".join(f"({a},{b})" for a, b in sorted(blocked))
    add(f"math_paths_{k}", "math",
        f"On an 8x8 grid of cells with coordinates (row,col) from (0,0) to (7,7), you start at (0,0) and want to reach (7,7) moving only down (row+1) or right (col+1). The following cells are blocked and cannot be entered: {bl}. How many distinct paths are there?" + ANS,
        "int", answer=dp[n-1][n-1])

# 2. digit-sum / coprime counting
for k in range(2):
    N = R.randrange(3000, 9000); M = R.choice([12, 30, 42, 70, 66]); d = R.choice([7, 9, 11])
    cnt = sum(1 for x in range(1, N + 1) if math.gcd(x, M) == 1 and sum(map(int, str(x))) % d == 0)
    add(f"math_count_{k}", "math",
        f"How many integers x with 1 <= x <= {N} satisfy both: gcd(x, {M}) = 1, and the sum of the decimal digits of x is divisible by {d}?" + ANS,
        "int", answer=cnt)

# 3. modular tower
for k in range(2):
    a, b, c = R.randrange(3, 20), R.randrange(3, 30), R.randrange(2, 6)
    m = 10000
    val = pow(a, b ** c, m)
    add(f"math_mod_{k}", "math",
        f"Compute the last four digits of {a}^({b}^{c}) (that is, {a} raised to the power {b**c}). Give the answer as an integer between 0 and 9999 (no leading zeros needed)." + ANS,
        "int", answer=val)

# 4. probability -> p+q
for k in range(2):
    reds, blues, draws = R.randrange(4, 8), R.randrange(3, 7), 4
    balls = ["R"] * reds + ["B"] * blues
    tot = Fraction(0); cnt = 0
    for combo in itertools.permutations(range(len(balls)), draws):
        cnt += 1
        seq = [balls[i] for i in combo]
        # event: at least 2 reds AND first draw blue
        if seq[0] == "B" and seq.count("R") >= 2:
            tot += 1
    p = tot / cnt
    add(f"math_prob_{k}", "math",
        f"An urn contains {reds} red and {blues} blue balls. Four balls are drawn one at a time without replacement. What is the probability that the first ball drawn is blue AND at least two of the four drawn balls are red? Write the probability as a reduced fraction p/q and report p+q." + ANS,
        "int", answer=p.numerator + p.denominator)

# 5. permutations with restrictions
for k, n in enumerate([7, 8]):
    c = 0
    for p in itertools.permutations(range(1, n + 1)):
        if any(p[i] == i + 1 for i in range(n)): continue
        if any(abs(p[i] - p[i+1]) == 1 for i in range(n - 1)): continue
        c += 1
    add(f"math_perm_{k}", "math",
        f"Count the permutations (p1, p2, ..., p{n}) of the numbers 1..{n} such that (a) no number is in its own position (pi != i for all i), and (b) no two adjacent entries differ by exactly 1 (|pi - p(i+1)| != 1 for all i)." + ANS,
        "int", answer=c)

# 6. bounded compositions
for k, (S, xm, ylo, yhi, md) in enumerate([(31, 12, 2, 15, 3), (44, 17, 5, 21, 4)]):
    c = sum(1 for x in range(0, xm + 1) for y in range(ylo, yhi + 1) for z in range(0, S + 1)
            if x + y + z == S and z % md != 0 and x != y)
    add(f"math_comp_{k}", "math",
        f"How many ordered triples of integers (x, y, z) satisfy x + y + z = {S}, with 0 <= x <= {xm}, {ylo} <= y <= {yhi}, z >= 0, z not divisible by {md}, and x != y?" + ANS,
        "int", answer=c)

# 7. calendar
d0 = datetime.date(2026, 10, 5)
for k in range(1):
    delta = R.randrange(5000, 20000)
    d1 = d0 + datetime.timedelta(days=delta)
    add(f"math_cal_{k}", "math",
        f"Monday, October 5, 2026 is day 0. What calendar date (YYYY-MM-DD) is day {delta}, and what weekday is it? Answer in the form YYYY-MM-DD Weekday." + ANS,
        "exact_ci", answer=f"{d1.isoformat()} {d1.strftime('%A')}")

# ---------------------------------------------------------------- LOGIC
def zebra(seed):
    rr = random.Random(seed)
    names = ["Alice", "Bob", "Chen", "Dana"]
    attrs = {"pet": ["cat", "dog", "fish", "bird"], "drink": ["tea", "coffee", "milk", "juice"],
             "color": ["red", "green", "blue", "white"]}
    sol = {"name": rr.sample(names, 4)}
    for a, v in attrs.items(): sol[a] = rr.sample(v, 4)
    cats = list(sol)
    allv = [(c, v) for c in cats for v in sol[c]]
    pos = {(c, v): sol[c].index(v) for c in cats for v in sol[c]}
    def gen_clue():
        t = rr.choice(["same", "left", "next", "pos", "not"])
        (c1, v1), (c2, v2) = rr.sample(allv, 2)
        if t == "same":
            c2 = rr.choice([c for c in cats if c != c1]); v2 = sol[c2][pos[(c1, v1)]]
            return ("same", c1, v1, c2, v2)
        if t == "left":
            p = rr.randrange(3); c1 = rr.choice(cats); c2 = rr.choice(cats)
            return ("left", c1, sol[c1][p], c2, sol[c2][p + 1])
        if t == "next":
            if abs(pos[(c1, v1)] - pos[(c2, v2)]) == 1: return ("next", c1, v1, c2, v2)
            return None
        if t == "pos":
            return ("pos", c1, v1, pos[(c1, v1)])
        if t == "not":
            if pos[(c1, v1)] != pos[(c2, v2)] and c1 != c2: return ("not", c1, v1, c2, v2)
            return None
    def holds(cl, asg):
        P = lambda c, v: asg[c].index(v)
        if cl[0] == "same": return P(cl[1], cl[2]) == P(cl[3], cl[4])
        if cl[0] == "left": return P(cl[1], cl[2]) + 1 == P(cl[3], cl[4])
        if cl[0] == "next": return abs(P(cl[1], cl[2]) - P(cl[3], cl[4])) == 1
        if cl[0] == "pos": return P(cl[1], cl[2]) == cl[3]
        if cl[0] == "not": return P(cl[1], cl[2]) != P(cl[3], cl[4])
    perms = {c: list(itertools.permutations(sol[c])) for c in cats}
    clues = []
    while True:
        cl = gen_clue()
        if cl is None or cl in clues: continue
        if cl[0] == "pos" and sum(1 for x in clues if x[0] == "pos") >= 1: continue
        clues.append(cl)
        sols = 0
        for combo in itertools.product(*[perms[c] for c in cats]):
            asg = dict(zip(cats, combo))
            if all(holds(x, asg) for x in clues):
                sols += 1
                if sols > 1: break
        if sols == 1: break
    def txt(cl):
        d = lambda c, v: {"name": f"{v}", "pet": f"the person with the {v}", "drink": f"the person who drinks {v}", "color": f"the person in the {v} house"}[c]
        if cl[0] == "same": return f"{d(cl[1], cl[2])} is the same person as {d(cl[3], cl[4])}."
        if cl[0] == "left": return f"{d(cl[1], cl[2])} lives directly left of {d(cl[3], cl[4])}."
        if cl[0] == "next": return f"{d(cl[1], cl[2])} lives next to {d(cl[3], cl[4])}."
        if cl[0] == "pos": return f"{d(cl[1], cl[2])} lives in house {cl[3] + 1}."
        if cl[0] == "not": return f"{d(cl[1], cl[2])} is not the same person as {d(cl[3], cl[4])}."
    clue_txt = "\n".join(f"{i+1}. {txt(c)}" for i, c in enumerate(clues))
    q_pet = rr.choice(attrs["pet"])
    who = sol["name"][sol["pet"].index(q_pet)]
    prompt = ("Four houses stand in a row, numbered 1 to 4 from left to right. Each house has one person (Alice, Bob, Chen, Dana), "
              "one pet (cat, dog, fish, bird), one drink (tea, coffee, milk, juice) and one color (red, green, blue, white); all values are distinct. "
              f"'Directly left of' means the house number is exactly one less.\n\nClues:\n{clue_txt}\n\n"
              f"Who owns the {q_pet}, and what does that person drink?" + "\n\nGive the final answer on the last line in the form: ANSWER: <name>, <drink>")
    return prompt, f"{who}, {sol['drink'][sol['name'].index(who)]}", len(clues)

for k in range(4):
    p, a, nc = zebra(100 + k)
    add(f"logic_zebra_{k}", "logic", p, "exact_ci", answer=a, meta={"clues": nc})

def knights(seed, n=6):
    rr = random.Random(seed)
    names = ["Ava", "Ben", "Cal", "Dee", "Eli", "Fay"][:n]
    while True:
        truth = [rr.random() < 0.5 for _ in range(n)]
        stmts = []
        for i in range(n):
            kind = rr.choice(["is", "same", "count", "or"])
            j, k2 = rr.sample([x for x in range(n) if x != i], 2)
            if kind == "is":
                v = rr.random() < 0.5
                f = (lambda j, v: lambda t: t[j] == v)(j, v)
                s = f"{names[j]} is a {'knight' if v else 'knave'}."
            elif kind == "same":
                f = (lambda j, k2: lambda t: t[j] == t[k2])(j, k2)
                s = f"{names[j]} and {names[k2]} are the same type."
            elif kind == "count":
                c = rr.randrange(1, n)
                f = (lambda c: lambda t: sum(t) == c)(c)
                s = f"Exactly {c} of us six are knights."
            else:
                f = (lambda j, k2: lambda t: (not t[j]) or (not t[k2]))(j, k2)
                s = f"At least one of {names[j]} and {names[k2]} is a knave."
            stmts.append((s, f))
        sols = [t for t in itertools.product([True, False], repeat=n) if all(t[i] == stmts[i][1](t) for i in range(n))]
        if len(sols) == 1:
            break
    t = sols[0]
    lines = "\n".join(f"{names[i]} says: \"{stmts[i][0]}\"" for i in range(n))
    prompt = ("On an island, knights always tell the truth and knaves always lie. Six inhabitants make these statements:\n"
              f"{lines}\n\nDetermine exactly which of them are knights. "
              "Give the final answer on the last line in the form: ANSWER: <comma-separated names of the knights in alphabetical order, or NONE>")
    ans = ", ".join(sorted(names[i] for i in range(n) if t[i])) or "NONE"
    return prompt, ans

for k in range(4):
    p, a = knights(200 + k)
    add(f"logic_knights_{k}", "logic", p, "set_ci", answer=a)

# ---------------------------------------------------------------- KNOWLEDGE MCQ (hand-written, verified answers)
MCQ = [
 ("Which of the following has the highest boiling point at 1 atm?\nA) n-pentane\nB) neopentane (2,2-dimethylpropane)\nC) isopentane (2-methylbutane)\nD) all three are equal", "A"),
 ("A photon has wavelength 500 nm. Approximately what is its energy?\nA) 1.24 eV\nB) 2.48 eV\nC) 3.10 eV\nD) 4.96 eV", "B"),
 ("In E. coli, which enzyme is primarily responsible for removing RNA primers during DNA replication?\nA) DNA polymerase III\nB) DNA ligase\nC) DNA polymerase I\nD) Primase", "C"),
 ("What is the hybridization of the central xenon atom in XeF4?\nA) sp3\nB) sp3d\nC) sp3d2\nD) dsp2", "C"),
 ("For an ideal gas undergoing a reversible adiabatic expansion, which quantity stays constant?\nA) Temperature\nB) Internal energy\nC) Entropy\nD) Enthalpy", "C"),
 ("Which treaty ended the Thirty Years' War?\nA) Treaty of Utrecht\nB) Peace of Westphalia\nC) Treaty of Versailles (1648)\nD) Peace of Augsburg", "B"),
 ("The group of rotational symmetries of a regular tetrahedron is isomorphic to:\nA) S4\nB) A4\nC) D6\nD) Z12", "B"),
 ("How many stereoisomers does 2,3,4-trihydroxyglutaric acid (HOOC-CH(OH)-CH(OH)-CH(OH)-COOH) have?\nA) 2\nB) 3\nC) 4\nD) 8", "C"),
 ("A ball is thrown straight up and experiences air resistance proportional to speed. Compared to the time going up, the time coming back down to the launch point is:\nA) shorter\nB) equal\nC) longer\nD) depends on mass only", "C"),
 ("Which of these complexes is expected to be diamagnetic?\nA) [Fe(H2O)6]2+\nB) [Fe(CN)6]4-\nC) [CoF6]3-\nD) [Mn(H2O)6]2+", "B"),
 ("The determinant of the n x n matrix with 2 on the diagonal, -1 on the sub- and super-diagonals, and 0 elsewhere is:\nA) 2^n\nB) n\nC) n+1\nD) 1", "C"),
 ("In a Hardy-Weinberg population, the frequency of a recessive phenotype is 0.09. What fraction of the population is heterozygous?\nA) 0.21\nB) 0.42\nC) 0.49\nD) 0.30", "B"),
]
for k, (q, a) in enumerate(MCQ):
    add(f"mcq_{k}", "knowledge", q + "\n\nGive the final answer on the last line in the form: ANSWER: <letter>", "letter", answer=a)

# ---------------------------------------------------------------- CODING
CODE = []
CODE.append(("merge_intervals",
 "Write a Python function `merge_intervals(intervals)` that takes a list of [start, end] integer pairs (start <= end, unsorted, possibly empty) and returns a new list of merged, sorted, non-overlapping intervals. Intervals that merely touch (e.g. [1,3] and [3,5]) must be merged.",
 """
assert merge_intervals([]) == []
assert merge_intervals([[1,3],[2,6],[8,10],[15,18]]) == [[1,6],[8,10],[15,18]]
assert merge_intervals([[1,4],[4,5]]) == [[1,5]]
assert merge_intervals([[5,7],[1,2],[2,3],[6,9]]) == [[1,3],[5,9]]
assert merge_intervals([[1,10],[2,3],[4,5]]) == [[1,10]]
assert merge_intervals([[0,0]]) == [[0,0]]
"""))
CODE.append(("regex_match",
 "Write a Python function `is_match(s, p)` implementing regular expression matching where '.' matches any single character and '*' matches zero or more of the preceding element. The match must cover the entire string. Do not use the `re` module.",
 """
import random
assert is_match("aa","a") is False
assert is_match("aa","a*") is True
assert is_match("ab",".*") is True
assert is_match("aab","c*a*b") is True
assert is_match("mississippi","mis*is*p*.") is False
assert is_match("","a*b*") is True
assert is_match("abcd","d*") is False
import re
rr = random.Random(1)
for _ in range(400):
    s = "".join(rr.choice("ab") for _ in range(rr.randrange(0,7)))
    p = ""
    for _ in range(rr.randrange(0,5)):
        p += rr.choice("ab.") + rr.choice(["","*"])
    assert is_match(s,p) == (re.fullmatch(p,s) is not None), (s,p)
"""))
CODE.append(("parse_duration",
 "Write a Python function `parse_duration(s)` that parses strings like '1h30m', '45s', '2d3h', '1h 15m 30s', '90m' into a total number of seconds (int). Units: d (days), h, m, s. Units may appear in any order but each at most once; whitespace between components is allowed. Raise ValueError for empty strings, unknown units, repeated units, missing numbers, or any other malformed input such as '1.5h' or 'h'.",
 """
assert parse_duration('1h30m') == 5400
assert parse_duration('45s') == 45
assert parse_duration('2d3h') == 2*86400+3*3600
assert parse_duration('1h 15m 30s') == 4530
assert parse_duration('30s 1m') == 90
assert parse_duration('0s') == 0
for bad in ['', 'h', '1x', '1h1h', '1.5h', '10', 'abc', '1h-2m', ' ']:
    try:
        parse_duration(bad); raise AssertionError('no error for '+repr(bad))
    except ValueError:
        pass
"""))
CODE.append(("lru",
 "Write a Python class `LRUCache` with `__init__(self, capacity)`, `get(self, key)` returning the value or -1 if absent, and `put(self, key, value)`. When inserting beyond capacity, evict the least recently used key. Both `get` (on hit) and `put` count as a use. Operations must be O(1) average.",
 """
c = LRUCache(2)
c.put(1,1); c.put(2,2)
assert c.get(1) == 1
c.put(3,3)
assert c.get(2) == -1
c.put(4,4)
assert c.get(1) == -1
assert c.get(3) == 3
assert c.get(4) == 4
c = LRUCache(1); c.put(1,1); c.put(1,5); assert c.get(1) == 5; c.put(2,2); assert c.get(1) == -1
c = LRUCache(2); c.put(1,1); c.put(2,2); c.put(1,10); c.put(3,3); assert c.get(2) == -1 and c.get(1) == 10
"""))
CODE.append(("topo",
 "Write a Python function `topo_order(n, edges)` that returns a topological ordering of nodes 0..n-1 for a directed graph given as a list of (u, v) edges meaning u must come before v. Among all valid orderings return the lexicographically smallest one. If the graph has a cycle, raise ValueError.",
 """
assert topo_order(3, []) == [0,1,2]
assert topo_order(4, [(3,0),(2,1)]) == [2,1,3,0]
assert topo_order(5, [(4,1),(1,0),(3,0)]) == [2,3,4,1,0]
try:
    topo_order(3, [(0,1),(1,2),(2,0)]); raise AssertionError
except ValueError: pass
assert topo_order(1, []) == [0]
"""))
CODE.append(("spiral",
 "Write a Python function `spiral(matrix)` that returns the elements of a 2D list in clockwise spiral order starting from the top-left. The matrix may be empty or non-square (e.g. a single row or single column).",
 """
assert spiral([]) == []
assert spiral([[1,2,3],[4,5,6],[7,8,9]]) == [1,2,3,6,9,8,7,4,5]
assert spiral([[1,2,3,4],[5,6,7,8],[9,10,11,12]]) == [1,2,3,4,8,12,11,10,9,5,6,7]
assert spiral([[1],[2],[3]]) == [1,2,3]
assert spiral([[1,2,3]]) == [1,2,3]
assert spiral([[1,2],[3,4],[5,6]]) == [1,2,4,6,5,3]
"""))
CODE.append(("table_fmt",
 "Write a Python function `fmt_table(rows)` where `rows` is a non-empty list of lists of strings, the first row being the header. Return a string rendering an ASCII table with these exact rules: each column's width is the max length of any cell in that column; cells are padded with one space on each side; numeric cells (strings that parse as float, e.g. '3', '-2.5') in non-header rows are right-aligned, all others left-aligned; the header is always left-aligned; there is a border line made of '+' at column boundaries and '-' elsewhere at the top, after the header, and at the bottom; content lines use '|' as separators. Lines are joined with '\\n' and there is no trailing newline. Rows shorter than the header are padded with empty cells.",
 """
out = fmt_table([['name','qty'],['apple','3'],['kiwi','12']])
exp = '+-------+-----+\\n| name  | qty |\\n+-------+-----+\\n| apple |   3 |\\n| kiwi  |  12 |\\n+-------+-----+'
assert out == exp, repr(out)
out = fmt_table([['a','b','c'],['x']])
exp = '+---+---+---+\\n| a | b | c |\\n+---+---+---+\\n| x |   |   |\\n+---+---+---+'
assert out == exp, repr(out)
out = fmt_table([['v'],['-2.5'],['abc']])
exp = '+------+\\n| v    |\\n+------+\\n| -2.5 |\\n| abc  |\\n+------+'
assert out == exp, repr(out)
"""))
CODE.append(("multiply_str",
 "Write a Python function `multiply(a, b)` that multiplies two non-negative integers given as decimal strings (possibly with leading zeros, possibly hundreds of digits) and returns the product as a decimal string without leading zeros ('0' for zero). You must not convert the whole strings to int (implement digit arithmetic yourself).",
 """
import random
assert multiply('0','12345') == '0'
assert multiply('000','0') == '0'
assert multiply('007','6') == '42'
rr = random.Random(3)
for _ in range(200):
    a = str(rr.randrange(0, 10**rr.randrange(1,120))); b = str(rr.randrange(0, 10**rr.randrange(1,120)))
    assert multiply(a,b) == str(int(a)*int(b))
"""))
CODE.append(("islands",
 "Write a Python function `count_islands(grid)` where grid is a list of strings of '#' (land) and '.' (water). Land cells are connected if they touch horizontally, vertically OR diagonally. Return the number of islands. Must handle grids up to 300x300 without hitting Python's recursion limit.",
 """
assert count_islands([]) == 0
assert count_islands(['#.#','.#.','#.#']) == 1
assert count_islands(['#..#','....','#..#']) == 4
assert count_islands(['##.','...','.##']) == 2
big = ['#'*300 for _ in range(300)]
assert count_islands(big) == 1
snake = [('#'*299+'.') if i%4==0 else ('.'*299+'#') if i%4==1 else ('.'+'#'*299) if i%4==2 else ('#'+'.'*299) for i in range(300)]
assert count_islands(snake) == 1
"""))
CODE.append(("interval_sched",
 "Write a Python function `max_weight_schedule(jobs)` where jobs is a list of (start, end, weight) tuples with integer times (start < end). Two jobs are compatible if one ends at or before the other starts. Return the maximum total weight of a set of mutually compatible jobs. Must run in O(n log n) for n up to 100000.",
 """
assert max_weight_schedule([]) == 0
assert max_weight_schedule([(1,3,5),(2,5,6),(4,6,5),(6,7,4),(5,8,11),(7,9,2)]) == 17
assert max_weight_schedule([(1,2,50),(3,5,20),(6,19,100),(2,100,200)]) == 250
assert max_weight_schedule([(0,1,1),(1,2,1),(2,3,1)]) == 3
import random, time
rr = random.Random(5)
jobs=[]
for _ in range(100000):
    s=rr.randrange(0,10**6); jobs.append((s, s+rr.randrange(1,1000), rr.randrange(1,100)))
t=time.time(); max_weight_schedule(jobs); assert time.time()-t < 5
small=[(rr.randrange(0,20),0,rr.randrange(1,9)) for _ in range(12)]
small=[(s, s+rr.randrange(1,6), w) for s,_,w in small]
best=0
import itertools
for m in range(1<<12):
    sel=[small[i] for i in range(12) if m>>i&1]
    sel.sort(key=lambda j:j[0])
    if all(sel[i][1]<=sel[i+1][0] for i in range(len(sel)-1)):
        best=max(best,sum(j[2] for j in sel))
assert max_weight_schedule(small)==best
"""))
for name, desc, tests in CODE:
    add(f"code_{name}", "code",
        desc + "\n\nReturn only the complete implementation in a single ```python code block (standard library only, no example usage or tests).",
        "python_tests", tests=tests)

# ---------------------------------------------------------------- INSTRUCTION FOLLOWING
IF = [
 ("if_nocomma", "Write a product description for a solar-powered bicycle lamp in 80 to 120 words. Do not use any commas anywhere in your response.", {"no_comma": True, "words": [80, 120]}),
 ("if_bullets", "List exactly 7 risks of migrating a monolith to microservices. Use markdown bullets starting with '- ', one per line, and nothing else: no title, no intro, no conclusion.", {"bullets": 7, "only_bullets": True}),
 ("if_json", "Return a JSON object (and nothing else, no code fences) describing a fictional book with keys: \"title\" (string), \"year\" (integer between 1900 and 2000), \"authors\" (array of exactly 2 strings), \"rating\" (number between 0 and 5), \"tags\" (array of 3 lowercase strings).", {"json_book": True}),
 ("if_lower_end", "Explain what a hash table is in 3 short paragraphs separated by blank lines. The entire response must be in lowercase letters only (no capital letters at all), and it must end with the exact phrase: that is all.", {"lowercase": True, "ends": "that is all.", "paragraphs": 3}),
 ("if_title_words", "Write a haiku about debugging. The first line of your response must be a title wrapped in double angular brackets, like <<title>>. Then the haiku as exactly 3 lines. Nothing else.", {"title": True, "lines_after_title": 3}),
 ("if_keyword", "Write a short paragraph (50-90 words) about coffee in which the word 'bean' appears exactly 3 times (case-insensitive, as a whole word; 'beans' does not count) and the letter 'z' never appears.", {"word_count_exact": ["bean", 3], "no_letter": "z", "words": [50, 90]}),
 ("if_german", "Antworte ausschließlich auf Deutsch in genau zwei Sätzen: Warum ist der Himmel blau? Verwende das Wort 'Streuung'.", {"sentences": 2, "contains": "Streuung", "german": True}),
 ("if_sections", "Write a mini incident report with exactly these three markdown headers in this order: '## Summary', '## Root Cause', '## Action Items'. Under Action Items, give exactly 3 numbered items (1., 2., 3.). Total length under 150 words.", {"headers": ["## Summary", "## Root Cause", "## Action Items"], "numbered": 3, "max_words": 150}),
]
for id, p, chk in IF:
    add(id, "instruct", p, "ifeval", checks=chk)

# ---------------------------------------------------------------- TOOL CALLING
WEATHER = {"type": "function", "function": {"name": "get_weather", "description": "Get current weather for a city",
           "parameters": {"type": "object", "properties": {"city": {"type": "string"}, "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}}, "required": ["city"]}}}
CONVERT = {"type": "function", "function": {"name": "convert_currency", "description": "Convert an amount between currencies",
           "parameters": {"type": "object", "properties": {"amount": {"type": "number"}, "from": {"type": "string", "description": "ISO code"}, "to": {"type": "string", "description": "ISO code"}}, "required": ["amount", "from", "to"]}}}
SEARCH = {"type": "function", "function": {"name": "search_files", "description": "Search files in the repository by regex",
           "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}, "path": {"type": "string"}, "max_results": {"type": "integer"}}, "required": ["pattern"]}}}
add("tool_single", "tools", "What's the weather in Reykjavik right now? Use fahrenheit.", "tool",
    tools=[WEATHER, CONVERT, SEARCH], expect={"calls": [{"name": "get_weather", "args": {"city": "reykjavik", "unit": "fahrenheit"}}]})
add("tool_parallel", "tools", "Convert 250 EUR to USD and also 1000 JPY to GBP. Do both conversions.", "tool",
    tools=[WEATHER, CONVERT, SEARCH], expect={"calls": [{"name": "convert_currency", "args": {"amount": 250, "from": "eur", "to": "usd"}},
                                                     {"name": "convert_currency", "args": {"amount": 1000, "from": "jpy", "to": "gbp"}}]})
add("tool_none", "tools", "What is 17 * 23? Answer directly.", "tool",
    tools=[WEATHER, CONVERT, SEARCH], expect={"calls": [], "content_contains": "391"})
add("tool_followup", "tools", "Find where the function `parse_config` is defined under src/, max 5 results.", "tool",
    tools=[WEATHER, CONVERT, SEARCH], expect={"calls": [{"name": "search_files", "args": {"path_contains": "src", "pattern_contains": "parse_config", "max_results": 5}}],
                                           "followup": {"result": "src/app/config.py:42: def parse_config(path: str) -> Config:", "content_contains": "config.py"}})

json.dump(T, open(os.path.join(os.path.dirname(__file__), "tasks.json"), "w"), indent=1)
from collections import Counter
print(len(T), Counter(t["cat"] for t in T))

# ---------------------------------------------------------------- LONG CONTEXT (aggregation over a big record dump)
def longctx(seed, n_records):
    rr = random.Random(seed)
    first = ["Mara","Jonas","Ines","Theo","Lena","Pavel","Yuki","Omar","Sofia","Ravi","Greta","Hugo","Nina","Felix","Aiko","Bruno","Clara","Dario","Elif","Farid"]
    last = ["Kowalski","Brandt","Okafor","Lindqvist","Moreau","Tanaka","Haddad","Novak","Ferreira","Iyer","Schmidt","Rossi","Dubois","Kim","Larsen","Mendes"]
    depts = ["Logistics","Finance","Research","Support","Legal","Sales","Facilities","Security","Marketing","Procurement"]
    target = "Quantum Optics"
    lines = []; total = 0; matches = []
    match_idx = set(rr.sample(range(n_records), 7))
    for i in range(n_records):
        eid = f"E{10000 + i*7 % 89999:05d}"
        name = f"{rr.choice(first)} {rr.choice(last)}"
        if i in match_idx:
            dept = target
            year = rr.choice([2016, 2017, 2019, 2021, 2023, 2024, 2018])
        else:
            dept = rr.choice(depts); year = rr.randrange(2005, 2026)
        sal = rr.randrange(41, 160) * 1000 + rr.choice([0, 250, 500, 750])
        city = rr.choice(["Graz","Lyon","Porto","Malmo","Bergen","Turin","Leeds","Ghent","Brno","Cork"])
        lines.append(f"- id={eid}; name={name}; dept={dept}; joined={year}; salary_eur={sal}; office={city}")
        if dept == target and year >= 2019:
            total += sal; matches.append(eid)
    doc = "\n".join(lines)
    q = (f"Below is an HR export with {n_records} employee records.\n\n{doc}\n\n"
         f"Question: What is the total salary_eur of all employees in the department '{target}' who joined in 2019 or later? "
         "List the matching ids, then give the final answer on the last line in the form: ANSWER: <integer>")
    return q, total, matches

for k, n in enumerate([350, 700, 1250]):
    q, tot, m = longctx(300 + k, n)
    add(f"long_{n}", "longctx", q, "int", answer=tot, meta={"matches": m, "records": n})

json.dump(T, open(os.path.join(os.path.dirname(__file__), "tasks.json"), "w"), indent=1)
from collections import Counter
print(len(T), Counter(t["cat"] for t in T))
