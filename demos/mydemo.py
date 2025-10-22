# This demo file contains all of the example code used in Zemla, Cao, Mueller, & Austerweil (under revision)

# These examples are used for exposition -- they use cases shown here are not
# always sensical. (For example, Example 4 shows how to compute letter fluency
# clusters, though the data is not letter fluency data.)

import snafu
import csv


# Import data for all categories of participants
fluencydata = snafu.load_fluency_data("fluency_data/filtered_snafu.csv",
                                      category="animals",
                                      removeNonAlphaChars=True,
                                      spell="../spellfiles/animals_snafu_spellfile.csv",
                                      hierarchical=True)

# Calculate the number of static cluster switches using an animal cluster scheme
#       - You may use another scheme file or create your own
#       - You may also use clustertype="fluid" (see Figure 1 in Zemla, Cao, Mueller, & Austerweil)
#       - Because the data is formatted hierarchically, the function calculates the number of switches per list and then averages over all lists per participant
#       - If the data are formatted non-hierarchically (set `hierarchical=False` in Example 2), it would return a meaure per-list instead of per-participant
#       - The same is true for other examples below
avg_num_cluster_switches = snafu.clusterSwitch(fluencydata.labeledlists, "schemes/animali.csv", clustertype="static")

# Calculates "switch rate" a.k.a. switches per item
avg_switch_rate = snafu.clusterSwitch(fluencydata.labeledlists, "../schemes/animali.csv", clustertype="static", switchrate=True)

# Calculate the average fluid cluster size using the first two letters of a word as category labels (letter fluency)
#       - This example shows how to calculate letter fluency clusters; the parameter `2` specifies to use the first two letters of each word as a cluster label
#       - You can also use a scheme file in place of an integer to use semantic fluency clusters, just as in snafu.clusterSwitch
avg_cluster_sizes = snafu.clusterSize(fluencydata.labeledlists, 2)

# Calculate the number of perseverations in each list of the dataset.
#       - Perseverations are calculated *after* spell-corrections (see `spell` parameter of Example 1)
#       - This may be important, particularly for data collected online where participants misspell a word and then purposefully correct it on the next line
avg_num_perseverations = snafu.perseverations(fluencydata.labeledlists)

# Return a list of perseverations found in each fluency list
#       - Perseverations are calculated *after* spell-corrections (see `spell` parameter of Example 1)
perseveration_list = snafu.perseverationsList(fluencydata.labeledlists)

# Find the number of intrusions using an animal category scheme
avg_num_intrusions = snafu.intrusions(fluencydata.labeledlists, "../schemes/animali.csv")

# Return a list of all intrusions in animal fluency data
intrusions_list = snafu.intrusionsList(fluencydata.labeledlists, "../schemes/animali.csv")

# Return all intrusions in letter fluency data by specifying the target letter
#       - The target letter is not case sensitive
intrusions_list_letter = snafu.intrusionsList(fluencydata.labeledlists, "a")

# Example 11: Returns the average word frequency per list (or participant) and a list of words not factored into this calculation (when missing is set to None)
avg_word_freq = snafu.wordFrequency(fluencydata.labeledlists, data="../frequency/subtlex-us.csv", missing=0.5)

# Example 12: Returns the averagea age-of-acquisition per list (or participant) and a list of words not factored into this calculation (when missing is set to None)
avg_aoa = snafu.ageOfAcquisition(fluencydata.labeledlists, data="../aoa/kuperman.csv", missing=None)

# grab order of subject ids and list nums
sub_list = fluencydata.subs
# if data is list-level instead of participant-level, you can use this instead
#sub_list, listnum_list = zip(*fluencydata.listnums)

# create a list of tuples, with each tuple being a row you can write to CSV
to_write = list(zip(
            sub_list,
            avg_num_cluster_switches,
            avg_switch_rate,
            avg_cluster_sizes,
            avg_num_perseverations,
            avg_num_intrusions,
            avg_word_freq[0],
            avg_aoa[0]
            ))

# write data to a file!
with open('stats.csv','w') as fo:
    for line in to_write:
        fo.write(",".join([str(i) for i in line]) + "\n")