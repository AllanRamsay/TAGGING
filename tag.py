#!/usr/bin/python

"""
TAG.PY: collection of tagging algorithms. mxltagger is a version of
the one we developed for Arabic.

Programs to support COMP34411 Natural Language Systems: these programs
have more comments in them than code that I write for my own use, but
it's unlikely to be enough to make them easy to understand. If you
play with them then I hope they will help with understanding the ideas
and algorithms in the course. If you try to read the source code,
you'll probably just learn what a sloppy programmer I am.
"""

import re
import copy
from useful import *
import a2bw
try:
    import server
    reload(server)
except:
    print "Couldn't import 'server.py'"

try:
    from nltk.tag import brill as nltkbrill
    from nltk.corpus import wordnet as wn
except:
    print "WORDNET NOT AVAILABLE ON THIS MACHINE"

import sys
import cPickle
import math

METERING = False
try:
    getroot = wn.morphy
except:
    getroot = lambda x, y: x

"""
Set BNC to point to the copy of the BNC on the machine where the
program is being run. My Mac seems to have two names, depending on
whether it's connected to the internet
"""

if usingMac():
    BNC = '/Users/ramsay/BNC'
else:
    BNC = '/opt/info/courses/COMP34411/PROGRAMS/BNC'
UDT = "/Library/WebServer/CGI-Executables/COMP34411/ud-treebanks-v1.1"
ENGLISH = "UD_English"
ARABIC = "100Kunstemmed.csv"

"""
I'm very lazily storing word:tag pairs as either two elements lists or
two element tuples, rather than specifying a class. This is a very
feeble attempt at doing things correctly by specifying constants as
the offsets into these items
"""
FORM = 0
TAG = 1

"""
Run the tagger on the testset, return precision, recall, f, confusion matrix

The tagger will have been trained to either leave ambiguous tags alone or to
pick the first choice. When we're testing we have to follow the same regime,
so we ask the tagger for its value of splitAmbiguousTags when preparing
the test data.
"""

XBODY = re.compile("(?P<det>any|every|no|some)(?P<noun>body|one|thing)")
def fixInput(text, top=True):
    if top and isinstance(text, str):
        text = text.split()
    fixed = []
    for w in text:
        if isinstance(w, str):
            if w == "men":
                w = "mans"
            m = XBODY.match(w)
            if m:
                yield m.group("det")
                yield m.group("noun")
            elif w.endswith("n&apos;t"):
                yield w[:-len("n&apos;t")]
                yield "not"
            else:
                yield w
        else:
            yield w[FORM]
        
BOUNDARYMARKER = "***************"

"""
This is useful if we're using the Prolog implementation of Brill retagging.

But at present I'm not using that in COMP34411 (I do think it's neater, and
it's easier to extend the set of templates, but I'm trying to stick to Python
for COMP34411)
"""
def brillFormat(l, out=sys.stdout):
    if not out == sys.stdout:
        out = open(out, 'w')
    s = """
:- abolish([wd/2, tag/2, tag/3, sf/2, pf/2]).
:- dynamic wd/2, tag/2, tag/3, sf/2, pf/2.

"""
    for i in range(0, len(l)):
        x = l[i]
        s = s+"""
wd(%s, '%s').
tag(%s, '%s').
tag('%s', '%s', %s).
"""%(i, x[0], i, x[2], x[2], x[1], i)
    out.write(s)
    if not out == sys.stdout:
        out.close()

WNTAGS = ["n", "v", "r", "a"]
BNCTAGS = {"n":"NN", "v":"VV", "a":"AJ", "r":"AV"}
INVBNCTAGS = {BNCTAGS[x]:x for x in BNCTAGS}

"""
You might think that asking morphy what it thinks for words that
aren't in the lexicon would be a good idea. The trouble is that you
don't get any probabilities associated with the various tags, so that
if you did

>>> askmorphy("dog")

you'd get 

{'VV': 0.5, 'NN': 0.5}

and it seems as though that's worse than relying on the suffixes
"""

def askmorphy(word):
    tags = {}
    for t in WNTAGS:
        x = wn.morphy(word.lower(), t)
        if x:
            tags[BNCTAGS[t]] = 1.0
    return normalise(tags)

"""
usePrefix is helpful for Arabic, but is positively damaging for
English
"""
def tagword(word, lexicon, usePrefix=False, useSuffix=True, arabic=False):
    word, dummy = normalform(word, False)
    try:
        return lexicon[word]
    except:
        if arabic and word.startswith("Al"):
            return {"NN":1.0}
        if usePrefix:
            tags0 = {}
            for i in range(3,0,-1):
                try:
                    tags0 = lexicon["%s-"%(word[i:])]
                    break
                except:
                    pass
        if useSuffix:
            tags1 = {}
            for i in range(3,0,-1):
                try:
                    tags1 = lexicon["-%s"%(word[-i:])]
                    break
                except:
                    pass
        if usePrefix and useSuffix:
            tags = {}
            for t in tags0:
                if t in tags1:
                    tags[t] = tags0[t]*tags1[t]
            if not tags == {}:
                return normalise(tags)
            tags = {}
            for t in tags0:
                tags[t] = tags0[t]
            for t in tags1:
                incTable(t, tags, n=tags1[t])
            if not tags == {}:
                return normalise(tags)
        if usePrefix:
            if not tags0 == {}:
                return tags0
        if useSuffix:
            if not tags1 == {}:
                return normalise(tags1)
        return {"NN":1}

"""
Several of the taggers require a dictionary extracted from the corpus.

The basic idea is pretty simple--just read the words and stick them in
a hash table. There are some fiddly bits about things that aren't
well-formed words, but overall it's pretty straightforward.
"""

class WORD:

    def __init__(self, form, tag):
        self.form = form
        self.tag = tag

    def __repr__(self):
        return "WORD('%s', '%s')"%(self.form, self.tag)

class TAGGER:

    def __init_():
        pass

    def __call__(self, text):
        return self.tag(text)

    def showConfusion(self, latex=False):
        print showConfusion(self.confusion, latex=latex)
 
"""
The taggers: in line with standard NLTK practice, a tagger is something
that has a definition of tag, where tag takes either a string (which it
promptly converts to a list ofr words) or a list of words and returns
a list of (word, tag) pairs.
"""

"""
This one's a bit more complicated. But it's also quite a bit more
accurate, so it's worth including.

We add statistics about how likely one tag is to be followed or
preceded by another (these are not the same thing turned round: the
likelihood that a determiner is followed by a noun is not the same as
the likelihood that a noun is preceded by a determiner).

Imagine that we have three words, W1, W2, W3, where each of these has
(to keep things simple) two possible tags, T11, T12, T21, T22, T31,
T32

We're interested in W2: it must have one of the tags T21 and T22, and
it must be preceded by either T11 or T12 and followed by either T31 or
T31. The likelihood that T21 is preceded by either T11 or T12 is
p(T11->T21)+p(T12->T21), and the likelihood that T22 is preced by
either T11 or T12 is p(T11->T22)+p(T12->T22), where p(Ti -> Tj) is the
probability of Ti being followed by Tj. So we can estimate how likely
T21 and T22 each are on the basis of the preceding context.

Exactly analogous arguments let us estimate how likely T21 and T22 are
on the basis of the following context. So we now have three ways of
estimating the likelihood of each tag--preceding context, dictionary
and following context. The obvious way of combining them is by
multiplying them, but it would be nice to be able to goive them
different weights in the calculation. In particular, it turns out that
the dictionary-based element has a disproportionate effect. You can't
weight the elements in a product by multiplying them by a constant; so
what I do is take the square root of the contribution from the
dictionary. The consequence of this is to even out the differences
between different frequencies, which seems to work out quite
nicely. There are probably better ways of doing it (and even if there
aren't, there are probably powers that would work better--there's no
obvious reason why PC*(DICT^0.5)*FC should be better than, say
(PC^0.9)*(DICT^0.43)*FC. There's an experiment to be done here, but I
haven't done it. PC*(DICT^0.5) works quite well, and that will do me
for now.

This is an alternative to using HMMs. Works better for me than HMMs, which is
why I'm including it rather than an HMM-based one.
"""

P = re.compile("(<p><.*>)|(^\*+$)")
SPLIT = re.compile("\s+|!!")

DASHTAGS = {
    "AJ0-AV0": "AJ0",
    "AJ0-NN1": "NN1",
    "AJ0-VVN": "VVD", 
    "AJ0-VVG": "VVG",
    "AVQ-CJS": "AVQ",
    "CJS-PRP": "CJS",
    "CJT-DT0": "CJT",
    "NN1-NP0": "NN1",
    "NN1-VVB": "NN1",
    "NN2-VVZ": "NN2",
    "VVD-VVN": "VVD",}

def readcorpus(top, switch=False, P=P):
    if "\n" in top:
        for l in top.split("\n"):
            yield l
    else:
        if os.path.isdir(top):
            for f in os.listdir(top):
                for l in readcorpus(os.path.join(top, f), switch=switch, P=P):
                    yield l
        else:
            for l in open(top):
                l = l.strip()
                if l == "" or (P and P.match(l)):
                    for i in range(4):
                        yield "%s\t%s"%(BOUNDARYMARKER, BOUNDARYMARKER)
                else:
                    try:
                        tag, form = SPLIT.split(l)
                        if switch:
                            tag, form = form, tag
                        try:
                            tag = DASHTAGS[tag]
                        except:
                            pass
                        if "ndash;" in form and tag == "CRD":
                            f1, f2 = form.split("ndash;")
                            yield "%s\t%s"%("CRD", f1)
                            yield "DASH\t-"
                            yield "%s\t%s"%("CRD", f2)
                        else:
                            m = XBODY.match(form)
                            if m:
                                yield("AT0\t%s"%(m.group("det")))
                                yield("NN1\t%s"%(m.group("noun")))
                            else:
                                yield "%s\t%s"%(tag, form)
                    except Exception as e:
                        if isinstance(e, GeneratorExit):
                            raise e
                        yield "%s\t%s"%(BOUNDARYMARKER, BOUNDARYMARKER)

def knownWord(w, d):
    return wn.morphy(w)

SPECIALS = {
    "-": "DASH",
    "APOS": "SS",
    "a": "AT0",
    "about": "PRP",
    "above": "PRP",
    "all": "DT0",
    "around": "PRP",
    "as": "AS",
    "at": "PRP",
    "away": "PRP",
    "below": "PRP",
    "for": "PRP",
    "how": "WHADV",
    "in": "PRP",
    "of": "OF",
    "on": "PRP",
    "over": "PRP",
    "since": "PRP",
    "so": "SO",
    "that": "THAT", 
    "there": "THERE",
    "to": "TO",
    "up": "PRP",
    "very": "VERY",
    }

ALTFORMS = {"'s" :"APOS"}
def normalform(form, tag, altforms=ALTFORMS):
    if "http" in form or "HTTP" in form:
        form = "http"
    if form.startswith("@") and len(form) > 1:
        form = "@WHO"
    if form.startswith("#") and len(form) > 1:
        form = "#WHAT"
    try:
        form = float(form.replace(",", ""))
        form = "NUM"
    except:
        pass
    if form == "On" and tag == "IN":
        tag = "ON"
    try:
        t = form.decode("ASCII")
    except:
        form = "EMOJ"
        tag = "EMOJ"
    if form == "NUM" and not tag == "CRD": 
        tag = "CRD"
    try:
        tag = SPECIALS[form.lower()]
        form = form.lower()
    except:
        pass
    try:
        tag = mergetags[tag]
    except:
        pass
    try:
        form = altforms[form]
    except:
        pass
    return form, tag
    
class BASETAGGER(TAGGER):

    sentenceSplitter = re.compile('<p><a name="\d*">')
    
    def __init__(self, corpus=BNC, N=None, subcorpus="", testsize=1000, tagsize=1000, preprocess=(lambda x, y: (x, y)), ambiguoustags=False, specials=SPECIALS, mergetags={}):
        if not subcorpus == "":
            if not subcorpus[0] == "/":
                subcorpus = "/%s"%(subcorpus)
            corpus += subcorpus
        if isstring(corpus):
            corpus = readcorpus(corpus)
            if METERING:
                print "Making mxltagger from %s"%(corpus)
        else:
            if METERING:
                print "Making mxltagger from %s pretagged items"%(len(corpus))
        self.lexicon = {BOUNDARYMARKER:{BOUNDARYMARKER:1}}
        self.tagsize = tagsize
        self.tagset = {}
        self.ftransitions = {}
        self.btransitions = {}
        self.trigrams = {}
        self.usePrefix = False
        self.useSuffix = True
        self.tags = {}
        self.training = []
        tagcounter = 0
        lastTag = "SS"
        if not N is None:
            try:
                N = len(corpus)-1
            except:
                pass
        window = []
        prev1 = False
        if isinstance(testsize, list):
            self.testset = testsize
        else:
            self.testset = []
        startsent = False
        for i, word in enumerate(corpus):
            if i == N:
                break
            if METERING and i%5000 == 0:
                if N:
                    print "Collecting words: %.2f %s %s"%(float(i)/float(N), i, N)
                else:
                    print "Collecting words: %s"%(i)
            try:
                tag, form = word.tag, word.form
            except:
                try:
                    tag, form = word.strip().split("\t")
                except:
                    try:
                        word = word.strip().split("\t")
                        form = word[1]
                        tag = word[4]
                    except:
                        try:
                            tag, form = word[TAG], word[FORM]
                        except:
                            continue
            tag = tag.upper()
            form, tag = normalform(form, tag)
            
            if tag == "UNC":
                continue
            if tag[0] in "VNA":
                tag = tag[:2]
            if not form == "I" and (form.istitle() or form.isupper()) and knownWord(form.lower(), self.lexicon) and not tag == "NP":
                form = form.lower()
            elif tag == "NP" and form.islower():
                tag = "NN"
            word = [form, tag]
            if isinstance(testsize, int) and i < testsize:
                self.testset.append(word)
                continue
            self.training.append(word)
            tag = tag[:self.tagsize]
            if not tag in self.tags:
                self.tags[tag] = tagcounter
                tagcounter += 1
            incTableN([form, tag], self.lexicon)
            for i in range(1, min(4, len(form))):
                incTableN(["-%s"%(form[-i:]), tag], self.lexicon)
                incTableN(["%s-"%(form[:i]), tag], self.lexicon)
            if len(window) == 3:
                  incTableN(["!!!".join([window[0][TAG], window[2][TAG]]), window[1][TAG]], self.trigrams)
                  incTableN([window[1][TAG], window[2][TAG]], self.ftransitions)
                  incTableN([window[2][TAG], window[1][TAG]], self.btransitions)
                  """
                  if i > 10000 and sum(self.lexicon[window[1][FORM]].values())*2000 > i:
                      incTableN([window[1][FORM], window[2][TAG]], self.ftransitions)
                  """
            if len(window) == 3:
                window = window[1:]+[word]
            else:
                window += [word]
            startsent = (form == BOUNDARYMARKER)
        """
        l = []
        for w in self.ftransitions.keys():
            if not w.isupper() and w in self.lexicon:
                l.append((sum(self.lexicon[w].values()), w))
        l.sort()
        for w in l[:-100]:
            del self.ftransitions[w[1]]
        """
        normalise2(self.lexicon)
        normalise2(self.trigrams)
        self.N = i
        return

    def default(self, word):
        if word.istitle():
            return {"NP":1}
        else:
            return {"NN":1}
        
    def tag(self, text, justTags=True, out=False):
        tags = []
        for word in fixInput(text):
            tags.append(tagword(word, self.lexicon, usePrefix=self.usePrefix, useSuffix=self.useSuffix))
        if justTags:
            return [sortTable(t)[0][0] for t in tags]
        else:
            return tags

class CTAGGER(TAGGER):

    def __init__(self, basetagger):
        self.basetagger = basetagger
        self.lexicon = basetagger.lexicon
        self.trigrams = basetagger.trigrams
            
    def tag(self, text, justTags=True, out=False):
        tags = [sortTable(t) for t in self.basetagger.tag(text, justTags=False)]
        contexts = []
        for i in range(len(tags)):
            try:
                c = "!!!".join([t[0][0] for t in [tags[i-1], tags[i+1]]])
                contexts.append(self.trigrams[c])
            except:
                contexts.append(None)
        ctags = []
        for tag, context in zip(tags, contexts):
            if len(tag) == 1:
                ctags.append(tag)
            else:
                ctag = {}
                for t, n in tag:
                    try:
                        v = context[t]*n
                        ctag[t] = v
                    except:
                        pass
                if ctag == {}:
                    ctag = tag
                else:
                    normalise(ctag)
                    ctag = sortTable(ctag)
                ctags.append(ctag)
        if justTags:
            ctags = [c[0][0] for c in ctags]
        return ctags
      
class NODE:

    def __init__(self, label, start=0, prob=0.0, name=False):
        self.label = label
        self.start = start
        self.prob = prob
        self.incoming = []
        self.backlink = False
        self.name = name

    def __repr__(self):
        return 'node(label:%s, start:%s, prob:%s)'%(self.label, self.start, self.prob)

class ARC:

    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.colour = "black"
        
    def __repr__(self):
        return 'arc(start:%s -> end:%s)'%(self.start, self.end)
        
LEXICON = {"a":{"det":1.0},
           "an":{"det":1.0},
           "arrow":{"noun":0.7, "verb":0.3},
           "he":{"pronoun":1.0},
           "flies":{"noun":0.5, "verb":0.5},
           "like":{"prep":0.5, "verb":0.5},
           "races":{"noun":0.6, "verb":0.4},
           "runs":{"noun":0.3, "verb":0.7},
           "shop":{"noun":0.6, "verb":0.4},
           "small":{"adj":1.0},
           "time":{"noun":0.6, "verb":0.4},}

TRANSITIONS = normalise2({"pronoun":{"noun":0.1, "verb":0.9},
                          "noun":{"noun":0.3, "verb":0.7, "det":0.3, "prep":0.1},
                          "verb":{"noun":0.8, "verb":0.2, "det":0.5, "prep":0.1},
                          "det":{"adj":0.4, "noun":0.6, "verb":0.05},
                          "prep":{"det":0.3, "adj":0.2, "noun":0.4, "verb":0.1},
                          "adj":{"adj":0.5, "noun":0.5, "verb":0.2},},)

def makeTagNetwork(text, lexicon=LEXICON, usePrefix=False, useSuffix=True):
    nodes = {}
    observations = []
    if type(text) == "str":
        text = text.split()
    for i in range(len(text)):
        observations.append(NODE(text[i], start=i, name="%s"%(i)))
    for i in range(len(text)):
        tags = tagword(text[i], lexicon, usePrefix=usePrefix, useSuffix=useSuffix)
        j = 0
        for tag in tags:
            n = NODE([text[i], tag], start=i, prob=tags[tag], name="%s-%s"%(i, tag))
            if i > 0:
                for p in nodes[i-1]:
                    n.incoming.append(ARC(p, n))
            try:
                nodes[i].append(n)
            except:
                nodes[i] = [n]
    for node in nodes:
        nodes[node].sort(key=lambda x: x.label)
    return nodes, observations

def makeTabular(nodes, observations, transitions=TRANSITIONS, eprobs=LEXICON):
    return ""
    s = r"""
\newpage
\scalebox{0.55}{
\setlength{\tabcolsep}{30pt}
\begin{tabular}{%s}"""%("c"*len(nodes))
    sep0 = ""
    for i in range(len(nodes)):
        col = nodes[i]
        s += r"""%s
    \begin{tabular}{c}"""%(sep0)
        sep1 = ""
        for j in range(len(col)):
            c = col[j]
            s += r"""
        %s\Rnode{%s}{%s (%.2f)}"""%(sep1, c.name, c.label, c.prob)
            sep1 = r"""\\\\\\
        """
        s += r"""
    \end{tabular}"""
        sep0 = """
    &"""
    s += r"""
\\\\\\\\\\\\\\
"""
    sep0 = ""
    for i in range(len(observations)):
        o = observations[i]
        s += r"%s\Rnode{%s}{%s}"%(sep0, i, o.label)
        sep0 = " & "
    s += r"""\\
\end{tabular}
"""
    for i in range(len(nodes)-1):
        col = nodes[i+1]
        for x in col:
            for y in x.incoming:
                try:
                    s += r"""
\ncline[linewidth=4pt,nodesep=5pt,linestyle=dotted,linecolor=%s]{->}{%s}{%s}\ncput*[npos=0.25,nrot=:U]{\textcolor{%s}{%.2f}}"""%(y.colour, y.start.name, x.name, y.colour, transitions[y.start.label][x.label])
                except:
                    pass
    for i in range(len(observations)):
        for n in nodes[i]:
            p = tagword(observations[i].label[TAG], eprobs)[n.label]
            if n == nodes[i][-1]:
                s += r"""
\ncline[linewidth=1pt,nodesep=5pt,linestyle=solid]{->}{%s}{%s}\ncput*[npos=0.5,nrot=:U]{%.2f}"""%(i, n.name, p)
            else:
                s += r"""
\nccurve[linewidth=1pt,nodesep=5pt,linestyle=solid,angleA=180,angleB=-135]{->}{%s}{%s}\ncput*[npos=0.25,nrot=:U]{%.2f}"""%(i, n.name, p)
    s += """}"""
    return s

def normaliseColumn(nodes):
    try:
        t = sum(n.prob for n in nodes)
        for n in nodes:
            n.prob = n.prob/t
    except:
        pass

def step(nodes, observations, i, eprobs=LEXICON, transitions=TRANSITIONS, write=sys.stdout.write):
    if i == 0:
        for n0 in nodes[i]:
            try:
                n0.prob = tagword(observations[0].label[TAG], eprobs)[n0.label]
            except:
                n0.prob = 0.00001
        if write:
            write(makeTabular(nodes, observations, eprobs=eprobs, transitions=transitions))
    else:
        for n in nodes[i]:
            p0 = -1
            for prev in n.incoming:
                prev.colour = "black"
                p = prev.start
                try:
                    p1 = p.prob*transitions[p.label[TAG]][n.label[TAG]]*math.sqrt(tagword(observations[i].label, eprobs)[n.label[TAG]])
                except:
                    p1 = 0.00001
                if p1 > p0:
                    p0 = p1
                    n.prob = p0
                    if n.backlink:
                        n.backlink.colour = "black"
                    n.backlink = prev
                    prev.colour = "red"
                if write:
                    write(makeTabular(nodes, observations, eprobs=eprobs, transitions=transitions))
                    try:
                        write(r"""

\medpara
Probability of going from %s to %s is %.4f*%.4f*%.4f (=%.4f)
"""%(p.label, n.label, p.prob, transitions[p.label][n.label], tagword(observations[i].label, eprobs)[n.label], p1))
                    except:
                        pass
                    if p1 == p0:
                        write(r"""

\noindent
(better than previous value)
""")
                    else:
                        write(r"""

\noindent
(not better than previous value)
""")
    normaliseColumn(nodes[i])

def step(nodes, observations, i, eprobs=LEXICON, transitions=TRANSITIONS, write=sys.stdout.write):
    if i == 0:
        if write:
            write(makeTabular(nodes, observations, eprobs=eprobs, transitions=transitions))
    else:
        for n in nodes[i]:
            p0 = -1
            for prev in n.incoming:
                prev.colour = "black"
                p = prev.start
                try:
                    p1 = p.prob*transitions[p.label[TAG]][n.label[TAG]]*math.sqrt(tagword(observations[i].label, eprobs)[n.label[TAG]])
                except:
                    p1 = 0.00001
                if p1 > p0:
                    p0 = p1
                    n.prob = p0
                    if n.backlink:
                        n.backlink.colour = "black"
                    n.backlink = prev
                    prev.colour = "red"
                if write:
                    write(makeTabular(nodes, observations, eprobs=eprobs, transitions=transitions))
                    try:
                        write(r"""

\medpara
Probability of going from %s to %s is %.4f*%.4f*%.4f (=%.4f)
"""%(p.label, n.label, p.prob, transitions[p.label][n.label], tagword(observations[i].label, eprobs)[n.label], p1))
                    except:
                        pass
                    if p1 == p0:
                        write(r"""

\noindent
(better than previous value)
""")
                    else:
                        write(r"""

\noindent
(not better than previous value)
""")
    normaliseColumn(nodes[i])

def steps(nodes, observations, eprobs=LEXICON, transitions=TRANSITIONS, out=sys.stdout):
    for col in nodes:
        for node in nodes[col]:
            node.prob = 0
            node.backlink = False
            for arc in node.incoming:
                arc.colour = "black"
    with safeout(out) as write:
        if write and not write == sys.stdout.write:
            write(r"""
\documentclass[12pt]{article}
\usepackage{pstricks, pst-node, pst-tree}
\usepackage{graphicx}
\usepackage{lscape}
\usepackage{defns}
\usepackage{geometry}
\oddsidemargin=1in
\evensidemargin=1in
\topmargin=-1in
\textheight=10.5in
\begin{document}
\begin{landscape}
""")
        for i in range(len(nodes)):
            step(nodes, observations, i, eprobs=eprobs, transitions=transitions, write=write)
        m = 0
        for n in nodes[len(nodes)-1]:
            if n.prob >= m:
                m = n.prob
                best = n
        path = []
        while True:
            arc = best.backlink
            path = [best]+path
            if not arc:
                break
            arc.colour = "blue"
            best = arc.start
        if write: 
            write(makeTabular(nodes, observations, eprobs=eprobs, transitions=transitions))
            if not write == sys.stdout.write:
                write(r"""
\end{landscape}
\end{document}
""")
    return path
    
def viterbi(text, lexicon=LEXICON, transitions=TRANSITIONS, out=sys.stdout, usePrefix=False, useSuffix=True):
    nodes, observations = makeTagNetwork(text, lexicon=lexicon, usePrefix=usePrefix, useSuffix=useSuffix)
    return steps(nodes, observations, eprobs=lexicon, transitions=transitions, out=out)

class VTAGGER(TAGGER):

    def __init__(self, basetagger):
        self.basetagger = basetagger
        self.lexicon = basetagger.lexicon
        self.ftransitions = basetagger.ftransitions
        self.usePrefix = basetagger.usePrefix
        self.useSuffix = basetagger.useSuffix
        normalise2(self.ftransitions)

    def tag(self, text, justTags=True, out=False):
        path = viterbi(list(fixInput(text)), lexicon=self.lexicon, transitions=self.ftransitions, out=out, usePrefix=self.usePrefix, useSuffix=self.useSuffix)
        if justTags:
            return [n.label[TAG] for n in path]
        else:
            return [[(n.label[TAG], n.prob)] for n in path]

def mxlnetwork(words, itags, probs):
    s = r"""
\newpage
\setlength{\tabcolsep}{0.6in}
\begin{tabular}{%s}
"""%("c"*len(words))
    s += " & ".join(words)+"\\\\[1in]\n"
    for i in range(max(len(t) for t in itags)):
        l = []
        for j, t in enumerate(itags):
            try:
                k = sorted(t.keys())[i]
                k = r"{\Rnode{R%s-%s}{%s: %.3f}}"%(j, i, k, t[k])
                l.append(k)
            except:
                l.append("")
        s += " & ".join(l)+"\\\\[1in]\n"
    s += r"""\end{tabular}
"""
    for x in probs:
        for y in probs[x]:
            if x.split("-")[1] < y.split("-")[1]:
                npos = 0.1
            else:
                npos = 0.75
            s += r"""
\ncline[linewidth=1pt,nodesep=5pt,linestyle=solid]{->}{%s}{%s}\ncput*[npos=%s,nrot=:U]{%.2f}"""%(x, y, npos, probs[x][y])
    return s+"\n"

def mxl(text, lexicon, ftransitions, btransitions, write=sys.stdout.write):
    if isinstance(text, str):
        text = text.split()
    text = [BOUNDARYMARKER]+text+[BOUNDARYMARKER]
    tagged = []
    prev = [BOUNDARYMARKER, lexicon[BOUNDARYMARKER]]
    itags = [tagword(w, lexicon) for w in text]
    probs = {}
    if write and not write==sys.stdout.write:
        write(r"""\documentclass{article}
\usepackage{pstricks, pst-node, pst-tree}
\usepackage{defns}
\usepackage{lscape}
\oddsidemargin=-1in 
\evensidemargin=-1in
\begin{document}
""")
    for i, tags0 in enumerate(itags[:-1]):
        """ i is the position of destination """
        tags1 = {}
        for j, t in enumerate(sorted(tags0.keys())):
            s = tags0[t]
            n = 0
            """
            i-1 is position of prev, we're looking at prev's k'th tag
            """
            for k, x in enumerate(prev):
                if i > 1:
                    Rjk = "R%s-%s"%(i-2, k)
                    if not Rjk in probs:
                        probs[Rjk] = {}
                try: 
                    n += prev[x]*ftransitions[x][t]
                    if i > 1:
                        probs[Rjk]["R%s-%s"%(i-1, j)] = ftransitions[x][t]
                except:
                    pass
            next = tagword(text[i+1], lexicon)
            for x in next:
                try: 
                    n += next[x]*btransitions[x][t]
                except:
                    pass
            if n > 0:
                s = s*(n**(1/2.0))
            else:
                s = s/sys.maxint
            if s > 0:
                tags1[t] = s
        normalise(tags1)
        prev = tags1
        itags[i] = tags1
        if tags1 == {}:
            print i, text[i-1:i+1]
            raise Exception("XXX")
        if write:
            write(mxlnetwork(text[1:-1], itags[1:-1], probs))
    if write and not write==sys.stdout.write:
        write(r"""
\end{document}
""")
    return itags[1:-1]
        
class MXLTAGGER(TAGGER):

    def __init__(self, basetagger):
        self.basetagger = basetagger
        self.lexicon = basetagger.lexicon
        self.ftransitions = basetagger.ftransitions
        normalise2(self.ftransitions)
        self.btransitions = basetagger.btransitions
        self.btransitions = False
        try:
            normalise2(self.btransitions)
        except:
            pass

    def tag(self, text, justTags=True, out=False):
        with safeout(out) as write:
            path = mxl(list(fixInput(text)), self.lexicon, self.ftransitions, self.btransitions, write=write)
        if justTags:
            k = []
            for i, n in enumerate(path):
                try:
                    k.append(sortTable(n)[0][0])
                except:
                    print text[i-2:i+2]
                    print path[i-2:i+2]
                    raise Exception("Empty tag in output of %s"%(self))
            return k
        else:
            return path
        
class COMBINEDTAGGER(TAGGER):

    def __init__(self, taggers):
        self.taggers = taggers
        self.lexicon = taggers[0].lexicon

    def tag(self, txt, justTags=True, out=False):
        alltagged = [tagger.tag(txt, out=out) for tagger in self.taggers]
        tagged1 = []
        for i in range(len(alltagged[0])):
            tags = {}
            best = -1
            for tagged in alltagged:
                incTable(tagged[i], tags)
            x = sortTable(tags)[0][0]
            tagged1.append((x, tags[x]))
        if justTags:
            return [w[0] for w in tagged1]
        else:
            return [[w] for w in tagged1]
                
"""
Given a list of taggers, where the first one is better (higher
precision) than the second, and the second is better than the third,
..., make a single tagger which tries them each in order.
"""
class BACKOFFTAGGER(TAGGER):

    def __init__(self, taggers):
        self.main = taggers[0]
        if len(taggers[1:]) == 1:
            self.backoff = taggers[1]
        else:
            self.backoff = BACKOFFTAGGER(taggers[1:])

    def tag(self, l, choices=False, out=False):
        if isstring(l):
            l = l.strip()
            if ' ' in l:
                return self.tag(l.split(' '), choices)
            t = self.main.tag(l, choices)
            if t[1]:
                return t
            else:
                return self.backoff.tag(l, choices)
        else:
            return [self.tag(x, choices) for x in l]
        
def testTagger(testset, tagger, showTest=False, out=sys.stdout):
    b = []
    right = 0.0
    total = 0.0
    tagger.confusion = {}
    tagger.wrong = {}
    tagger.alltags = {}
    tagger.tagged = {}
    tagged = tagger.tag(testset, out=out)
    alltagged = zip(tagged, testset)
    for tag0, test in alltagged:
        tagTest = test[TAG]
        try:
            tag0 = sortTable(tag0)[0][0]
        except:
            pass
        if tag0 == BOUNDARYMARKER or tag0 == "UNC":
            continue
        if tag0 == tagTest:
            right += 1
        else:
            incTableN([test[FORM]], tagger.wrong)
        try:
            if not test[FORM] in tagger.lexicon:
                try:
                    tagger.unknown += 1
                except:
                    tagger.unknown = 1
        except:
            pass
        incTableN([tagTest, test[FORM], tag0], tagger.tagged)
        incTableN([test[FORM], tagTest, tag0], tagger.alltags)
        total += 1.0
        if not tagTest in tagger.confusion:
            tagger.confusion[tagTest] = {}
        if not tag0 in tagger.confusion[tagTest]:
            tagger.confusion[tagTest][tag0] = {}
        incTable(test[FORM], tagger.confusion[tagTest][tag0])
    p = right/total
    tagger.score = p
    return alltagged

def showTest(alltagged):
    last = False
    for x, y in alltagged:
        if x == BOUNDARYMARKER and last == BOUNDARYMARKER:
            continue
        last = x
        print "%s\t%s\ttagged: %s%s"%(y[0], y[1], x, "\t!!!!!" if not y[1]==x else "")

def fullTest(T=5000, i=10000, N=2000000, corpus=BNC, subcorpus="", mergetags={}, timing=False):
    METERING = False
    alltaggers = []
    sink = dummywriter()
    taggertypes = [("base tagger", BASETAGGER), 
                   ("vtagger", VTAGGER),
                   # ("mtagger", MXLTAGGER), 
                   ("ctagger", CTAGGER)] 
    print "training size (K)%s\txtagger\tknown words\tlexicon\tftransitions\ttrigrams"%("\t".join([x[0] for x in taggertypes]))
    prev = 0
    while True:
        if timing: print "TRAINING"
        if isinstance(T, int):
            j = i+T
        else:
            j = i
        btagger = BASETAGGER(corpus=corpus, subcorpus=subcorpus, testsize=T, N=j, mergetags=mergetags)
        if len(btagger.training) == prev:
            break
        prev = len(btagger.training)
        btagger.unknown = 0
        others = [x[1](btagger) for x in taggertypes[1:]]
        xtagger = COMBINEDTAGGER(others)
        taggers = [btagger]+others+[xtagger]
        alltaggers.append(taggers)
        if timing: print "TESTING"
        for t in taggers:
            t0 = now()
            alltagged = testTagger(btagger.testset, t, out=sink)
            if timing: print "%s words/sec for %s"%(int(T/timeSince(t0)), t)
        f = "\t%.3f"*len(taggers)
        print ("%s"+f+"\t%.3f"+("\t%s"*3))%tuple([i/1000]+[t.score for t in taggers]+[1-float(btagger.unknown)/len(btagger.testset), len(btagger.lexicon), len(btagger.ftransitions), len(btagger.trigrams)])
        if i == N:
            break
        i = 2*i
        if i > N:
            i = N
    return alltaggers

"""
showConfusion just lays out the confusion matrix reasonably neatly.
If latex is set to True, then the output is appropriate latex source
code.
"""
def showConfusion(c, latex=True, n=1000):
    if latex:
        s = r'\begin{tabular}{|c'+('|c'*len(c))+'|}\n\\hline\n'
        s = s+'\\end{tabular}\n'
    else:
        s = ""
    for t1 in sorted(c.keys()):
        l0 = c[t1]
        t = float(sum(sum(x.values()) for x in l0.values()))
        l0 = reversed(sorted([[sum(l0[x].values()), x] for x in l0]))
        l1 = ["%s, %s (%.3f)"%(x[1], x[0], x[0]/float(t)) for x in l0]
        if latex:
            s = s+"%s&%s\\\\\n"%(t1, "&".join(l1))
        else:
            s = s+"%s\t%s\n"%(t1, ", ".join(l1))
    if latex:
        s = s+'\\end{tabular}\n'
    return s

def badwords(allwords):
    b = []
    for x in allwords:
        n = 0
        for t in allwords[x]:
            if len(allwords[x][t]) > 1:
                for k in allwords[x][t]:
                    if not k == t:
                        n = max(allwords[x][t][k], n)
        if n > 0:
            b.append((n, x, allwords[x]))
    return sorted(b)

"""
Converters
"""
def readfahad(ifile="100KAgreed+PATB.txt", sep=",|\t"):
    c = []
    sep = re.compile("(?P<form>\S*)(%s)(?P<tag>\S*)(\s|$)"%(sep))
    for x in open(ifile):
        c += [(BOUNDARYMARKER, BOUNDARYMARKER)]*2
        for i in sep.finditer(x.strip()):
            form, tag = normalform(i.group("form"), i.group("tag"))
            c.append([form, tag])
    return c

def readGS(gsfile="GoldStandard.csv"):
    gs = []
    for x in open(gsfile):
        form, tag = x.strip().split(",")
        form = a2bw.convert(form.decode("UTF-8"), a2bw.a2bwtable)
        form, tag = normalform(form, tag)
        if form == "NUM": print tag
        if tag == "NNP":
            tag = "NN"
        gs.append([form, tag.upper()])
    return gs

def readOriginal(original="GoldStandardOriginal.txt"):
    words = []
    for l0 in open(original):
        l1 = []
        for x in a2bw.convert(l0.strip().decode("UTF-8")).split():
            while x[0] in ".@":
                l1.append(x[0])
                x = x[1:]
                if x == "":
                    break
            if not x == "":
                l1.append(x)
        words.append(l1)
    return words
            
def unstem(l, N=-1, out=False):
    w = ""
    t = ""
    addingPrefixes = True
    newWord = True
    words = []
    prefixes = set(["CC", "ART", "TNS", "FUT"])
    suffixes = set(["AGR", "AC", "PERS", "SPRP", "USERN"])
    TAG = False
    sep = re.compile(",|\t")
    with safeout(out) as write:
        for i, k in enumerate(l): 
            if i == N:
                return words
            try:
                [form, tag] = k
            except:
                k = k.strip()
                if k == "":
                    continue
                elif k == BOUNDARYMARKER:
                    if out:
                        write(k+"\n")
                    else:
                        words.append(k)
                    continue
                try:
                    form, tag = sep.split(k)
                except:
                    continue
                if tag == "\n":
                    continue
            if tag in prefixes or (tag == "IN" and len(form) == 1):
                if tag == "ART" and form == "al":
                    form = "Al"
                if addingPrefixes:
                    w += form
                else:
                    if out:
                        write("%s\t%s\n"%(TAG, w))
                    else:
                        words.append([w, TAG])
                    addingPrefixes = True
                    w = form
                    TAG = False
            elif tag in suffixes:
                w += form
            else:
                if TAG == False:
                    w += form
                    addingPrefixes = False
                    TAG = tag
                else:
                    if out:
                        write("%s\t%s\n"%(TAG, w))
                    else:
                        words.append([w, TAG])
                    w = form
                    if form in prefixes:
                        TAG = False
                        addingPrefixes = True
                    else:
                        TAG = tag
                        addingPrefixes = False
        if TAG:
            if out:
                write("%s\t%s\n"%(TAG, w))
            else:
                words.append([w, TAG])
    return words

def insertbreaks(original, goldstandard):
    words = []
    for x in original:
        while not goldstandard == []:
            y = goldstandard[0]
            if x[0] == y[0]:
                words += [[BOUNDARYMARKER, BOUNDARYMARKER]]*2
                break
            words.append(y)
            goldstandard = goldstandard[1:]
    return words

def savecorpus(corpus, out=sys.stdout):
    with safeout(out) as write:
        for x in corpus:
            write("%s\t%s\n"%(x[1], x[0]))

def splitrootandaffix(form, root):
    for i in range(min(len(form), len(root))):
        if not form[i] == root[i]:
            break
    return root, form[i+1:]

def reAltTags(alttags):
    for k in alttags.keys():
        alttags[k] = [x.split("->") for x in alttags[k]]
        alttags[k] = [(re.compile(x[0]), x[1]) for x in alttags[k]]
    return alttags

ALTTAGS = reAltTags({"VV": ["t->ed", "ng->ing", "(.ed|.*(n|d)|e|m)->ed", ".*s->s", "(me|ok|ent|.*ght|ke|w)->ed1"],
                     "NN": ["(ce|ren|n|.*s)->s"],
                     "AJ": [".*er->er", ".*est->est"],
                     "AV": []})

def posttag(tagged0, alttags=ALTTAGS):
    tagged1 = []
    usetagforword = set(["CRD", "ORD", "PRP"])
    fixed = set(["one", "can", "may", "European", "Europeans"])
    for form, tag in tagged0:
        if form in fixed:
            tagged1.append(form)
            continue
        try:
            root = wn.morphy(form, INVBNCTAGS[tag])
            if root:
                root, affix = splitrootandaffix(form, root)
            else:
                root, affix = form, ''
            for alt in alttags[tag]:
                if alt[0].match(affix):
                    affix = alt[1]
                    break
            tagged1.append([root, tag, affix])
        except:
            if tag in usetagforword:
                tagged1.append([form, tag])
            else:
                tagged1.append(form)
    return tagged1

def words2sentences(words, N=-1):
    i = 0
    sentence = []
    for w in words:
        try:
            tag, form = w.split("\t")
        except:
            [form, tag] = w
        if form == BOUNDARYMARKER:
            if not sentence == []:
                yield sentence
                i += 1
                if i == N:
                    return
                sentence = []
        else:
            sentence.append([form, tag])
            
def tagForProlog(sentences, tagger, out=sys.stdout):
    if isinstance(sentences, str):
        sentences = [sentences]
    with safeout(out) as write:
        for sentence in sentences:
            sentence = sentence.strip()
            if sentence == "":
                continue
            sentence = ["mans" if x == "men" else x for x in fixInput(sentence)]
            if isinstance(sentence, list):
                sentence = " ".join(x for x in sentence)
            if not sentence == "":
                tagged = posttag(zip(sentence.split(), tagger(sentence)))
                write("tagged('%s', %s).\n"%(sentence, tagged))
           
def startTaggerAsServer(tagger, servercount=5):
    server.startServers(servercount=servercount, action=lambda x: "%s."%(tagger(x)))
    server.startListening()

if "tag.py" in sys.argv[0]:
    startTaggerAsServer(fullTest()[-1][-2])

def readDets(corpus=BNC, N=1000000):
    tags = {}
    window = []
    dets = set(["a", "an", "every", "some", "the", "all", "each", "any", "most", "many", "much", "few", "one", "two", "three", "four", "five", "your", "my", "his", "their"])
    alldets = dets.union(set(["of"]))
    dets = set(["at"])
    alldets = set(["most", "least"])
    for w in readcorpus(BNC):
        tag, form = w.split("\t")
        if len(window) < 8:
            window.append((form, tag))
        else:
            (form0, tag0) = window[2]
            (form1, tag1) = window[3]
            if form0 in dets and form1 in alldets:
                if not form0 in tags:
                    tags[form0] = {}
                if not form1 in tags[form0]:
                    tags[form0][form1] = []
                if len(tags[form0][form1]) < 20:
                    tags[form0][form1].append(window)
            window = window[1:]+[(form, tag)]
        N -= 1
        if N < 0:
            break
    return tags

def getTuple(p, corpus=BNC, N=1000000000, prewindow=4, postwindow=4):
    if isinstance(p, str):
        print r"{\small\begin{verbatim}"
        p = re.compile("(\S*?!!\S*?\n){,%s}"%(prewindow)+"(?P<target>%s)"%(p)+"(\S*?!!\S*?\n){,%s}"%(postwindow), re.DOTALL)
    if os.path.isdir(corpus):
        for f in os.listdir(corpus):
            N = getTuple(p, os.path.join(corpus, f), N)
            if N == 0:
                break
    else:
        for i in p.finditer(open(corpus).read()):
            t = i.group(0).replace(i.group("target"), "*** %s***\n"%(i.group("target")))
            t = re.compile("\S*!!").sub("", t.replace("\n", " ")).strip()
            b = 0
            while not t[b:].startswith("***"):
                b += 1
            if b < 40:
                t = " "*(40-b)+t
            else:
                t = t[b-40:]
            print "%s"%(t)
            # print "%s: %s"%(t, corpus)
            N -= 1
            if N == 0:
                print r"\end{verbatim}}"
                break
    return N

def showDets1(r):
    for k in r:
        k = [":".join(w) for w in k]
        p = " ".join(k[:2])
        s = " ".join(k[2:])
        while len(p) < 30:
            p += " "
        print "  %s %s"%(p, s)
        
def showDets(dets):
    for x in sorted(dets.keys()):
        for y in sorted(dets[x].keys()):
            print "%s %s"%(x, y)
            showDets1(dets[x][y][:10])
