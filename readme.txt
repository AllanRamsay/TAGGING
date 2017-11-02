tag.py provides a range of classes of taggers:

BASETAGGER: dictionary of words and their most frequent tags and 1-,
2-, and 3-letter initial and final strings. Just look up the word, and
if you don't find it look up its initial and final subsequences and
make some combination of these. Typically, using the initial
subsequence doesn't help very much even for Arabic.

MXLTAGGER: this one multiplies the probability of a word having a tag
by the transition probabilities to all the preceding and following
possibilities and selects the most likely. It's quite good, but, at
least as I presently have it implemented, it's by far the slowest.

HMMTAGGER: er, it's an HMM. Emission probabilities are calculated as
in the BASETAGGER, transition probs are just collected. No need for
any fancy Baum-Welch reestimation. All the probabilities we need can
just be collected.

CTAGGER: we have a table that says how likely the word between a given
pair of tags is to have a specific tag. That's hard to read, what do I
actually mean? What, for instance, is the most likely thing to occur
between a determiner and a noun? We look up "AT!!!NN" in the table and
it says [('AJ', 0.53), ('NN', 0.29), ('NP', 0.09), ('ORD', 0.03),
('PUQ', 0.01), ('DT0', 0.01), ('CRD', 0.01)]. In other words, if
you've got a determiner and then something and then a noun, there's a
53% chance that the thing in the middle is an adjective, a 29% chance
that it's a noun, and so on. What if the thing in the middle had been
"love"? The distribution of tags for "love" is [('NN', 0.75), ('VV',
0.25)]. Multiply each suggestion made by the context by the intrinsic
probabilities for the word, highest is the best choice. This is
infuriatingly simple but it works *really* well for English.

COMBINEDTAGGER: take a set of taggers and combine their results on the
basis of which one is most confident for each word. This can help if
one of the taggers is generally pretty good but it makes some set of
systematic error. Obviously it is slower than the others -- if you
combine three taggers X, Y, Z that take TX, TY and TZ seconds/word then this
one will do then this one will take TX+TY+TZ seconds.

If you do

taggers = fullTest(corpus=ARABIC)

then you will get a big array of taggers trained on varying amounts of
data, where taggers[0] is all the taggers that were created at the
first round and taggers[-1] is all the taggers that were created at
the final round. So if you wanted, for instance, the HMM tagger that
was created with 1280K of data you'd say

>>> tagger = taggers[-2][1]

Training takes a little while, restoring a cPickled copy of a tagger
is quicker (though not instant, because there's a lot of data in the
lexicons and all of that has to be re-read).

The accuracy for the various taggers for varying amounts of training
data for Arabic tweets (based on Fahad's training data, which is not
actually perfectly representative of his twitter data, so these
accuracies may be a bit optimistic).

size	base 	vtagger	ctagger	xtagger	known 	lexicon	ftransitions	trigrams
10K	0.812	0.809	0.808	0.803	0.688	8355	26	263
20K	0.833	0.824	0.826	0.825	0.735	13582	28	321
40K	0.854	0.837	0.850	0.844	0.776	21062	30	372
80K	0.873	0.848	0.866	0.855	0.816	32437	33	435
160K	0.894	0.858	0.876	0.861	0.852	50316	36	498
320K	0.907	0.861	0.895	0.876	0.880	77152	37	554
640K	0.964	0.918	0.949	0.931	1.000	94545	39	605
1280K	0.964	0.911	0.947	0.926	1.000	130371	40	687
2000K	0.964	0.911	0.946	0.926	1.000	131156	40	689

size is amount of training data
base is the simple dictionary based one
vtagger is HMM
ctagger is context-tagger
xtagger is the combination of vtagger and ctagger
known is the proportion of words in the test data that are in the base
tagger's dictionary
lexicon is the size of that dictionary
ftransitions and trigrams are the stats used by the HMM and the
context-tagger

For Arabic, on Fahad's training data, there are no unknown words once
the training data reaches 640K, and all the way down actually the base
tagger is the best.

For English I get a slightly different picture:

10	0.890	0.909	0.907	0.907	0.880	3654	41	703
20	0.909	0.929	0.926	0.927	0.918	4782	41	843
40	0.925	0.944	0.945	0.945	0.942	8618	41	960
80	0.933	0.955	0.953	0.955	0.958	13121	42	1110
160	0.939	0.957	0.958	0.960	0.967	18985	43	1290
320	0.943	0.954	0.958	0.957	0.975	25913	44	1449
640	0.946	0.957	0.962	0.959	0.983	38262	44	1510
1280	0.949	0.960	0.966	0.963	0.987	54962	44	1598
2000	0.950	0.963	0.967	0.965	0.990	75248	44	1631

This is based on the BNC, for which the context-tagger seems to be the
best (better, indeed, than the combination with the HMM).

Speeds:

70345 words/sec for <__main__.BASETAGGER instance at 0x1bdbf5ea8>
16692 words/sec for <__main__.VTAGGER instance at 0x1c193e440>
62277 words/sec for <__main__.CTAGGER instance at 0x1c193e0e0>
14079 words/sec for <__main__.COMBINEDTAGGER instance at 0x1c193e4d0>

So a bit faster than Fahad's.

>>> print showConfusion(tagger.confusion, latex=False)

will tell you about what it gets wrong. For Arabic it seems that the
biggest sets of errors are that it gets adjectives muddled up with
nouns and it gets mentions muddled with replies (28 of each are wrong):

JJ	JJ, 184 (0.848), NN, 28 (0.129), VB, 5 (0.023)
MEN	MEN, 30 (0.517), REP, 28 (0.483)

These don't matter for stemming -- we don't attempt to stem mentions
or repeats, the stemming for adjectives and nouns is the same. You can
tell the tagger to treat certain tags as being equivalent by doing 

>>> taggers = fullTest(corpus=ARABIC, mergetags={"JJ":"NN", "REP":"MEN"})

That, obviously enough, improves the reported accuracy on the things
that it was getting wrong -- all adjectives, including the ones that
used to be wrongly tagged as nouns, are now correctly tagged as
nouns. Doing this can have unexpected knock-on effects on other words
(because their contexts may be less fine-grained and hence less
helpful). Without merging we had

VB	VB, 640 (0.976), NN, 15 (0.023), JJ, 1 (0.002)

Afterwards we had

VB	VB, 633 (0.965), NN, 23 (0.035)

Fewer verbs are recognised correctly if we blur the distinction
between nouns and adjectives. So it goes.


