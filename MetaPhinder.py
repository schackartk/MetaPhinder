#!/usr/bin/env python3

from __future__ import division
import argparse
import sys
import os


# ----------------------------------------------------------------------------
def get_args():
    """ Parse command line arguments"""

    parser = argparse.ArgumentParser(
        description='Classify metagenomic contigs as phage or not',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('-i',
                        '--infile',
                        metavar='FILE',
                        type=argparse.FileType('rt'),
                        help="Input FASTA file",
                        required=True)
    parser.add_argument('-o',
                        '--outpath',
                        metavar='DIR',
                        type=str,
                        help="Path to output file(s)",
                        default='.')
    parser.add_argument('-d',
                        '--database',
                        metavar='DB',
                        type=str,
                        help="MetaPhinder database",
                        required=True)
    parser.add_argument('-b',
                        '--blast',
                        metavar='BLAST',
                        type=str,
                        help="Path to BLAST installation",
                        required=True)
    
    return parser.parse_args()


# ----------------------------------------------------------------------------
def get_contig_size(contigfile):
    """ Calculate contig lengths """

    contigID = []
    size = {}
    s = -1

    for l in contigfile:
        l = l.strip()
        if l[0] == ">":

            # save size of previous contig:
            if s != -1:
                size[contigID[-1]] = s
                s = 0
            # save ID of new contig:
            l = l.split(" ")
            contigID.append(l[0].strip(">"))
        else:
            # count bases
            if s == -1:
                s = 0
            s = s + len(l)
    contigfile.close()

    # save size of last contig:
    if s == -1:
        sys.stderr.write("No contigs found! Problem with FASTA file format\n")
        sys.exit(2)
    else:
        size[contigID[-1]] = s

    return contigID, size


# ----------------------------------------------------------------------------
def calc_a_id(p_id, aln_l):
    """ Calculate ANI """

    tot_aln_l = 0
    a_id = 0
    for i in range(0, len(p_id)):
        a_id = a_id + (p_id[i] * aln_l[i])
        tot_aln_l = tot_aln_l + aln_l[i]

    if (tot_aln_l > 0 and a_id > 0):
        a_id = (a_id / tot_aln_l) / 100
    return a_id


# ----------------------------------------------------------------------------
def calc_rel_mcov(positions, gsize):
    """ Genome-wide % Identity """

    # calculate merged coverage:
    mcov = 0
    rel_mcov = 0

    if len(positions) > 1:
        spos = sorted(positions, key=lambda firstp: firstp[0])

        start = spos[0][0]
        end = spos[0][1]
        for i in range(0, (len(spos) - 1)):
            if spos[i + 1][0] > end:
                mcov += end - start
                start = spos[i + 1][0]
                end = spos[i + 1][1]
            else:
                if spos[i + 1][1] > end:
                    end = spos[i + 1][1]

        mcov += end - start
    # only one hit:
    elif len(positions) == 1:
        mcov = positions[0][1] - positions[0][0]

    rel_mcov = float(mcov) / gsize

    return rel_mcov


# ----------------------------------------------------------------------------
def main():
    """ Main function """

    print("parsing commandline options...")

    args = get_args()

    # open input file:
    if args.infile != None:
        contigfile = args.infile
    else:
        sys.stderr.write("Please specify inputfile!\n")
        sys.exit(2)

    # save outfile:
    if args.outpath != None:
        if args.outpath[-1] != "/":
            outPath = args.outpath + "/"
        else:
            outPath = args.outpath

    else:
        outPath = ""

    # save databasepath:
    if args.database != None:
        blastDB = args.database
    else:
        sys.stderr.write("Please specify path to database!\n")
        sys.exit(2)

    # save path to nnlinplayer:
    if args.blast != None:
        if args.blast[-1] != "/":
            blastPath = args.blast + "/"
        else:
            blastPath = args.blast
    else:
        blastPath = ""

    ################################################################################
    #   GET CONTIG LENGTH
    ################################################################################

    contigID, size = get_contig_size(contigfile)

    ################################################################################
    #   RUN BLAST
    ################################################################################

    print("running BLAST...")

    os.system(blastPath + "blastn -query " + contigfile.name +
              " -task blastn -evalue 0.05 -outfmt 7  -num_threads 4 -db " +
              blastDB + " -out " + outPath + "blast.out")

    ################################################################################
    #   PARSE BLAST OUTPUT
    ################################################################################

    print("calculating ANI...")

    res = {}  #results
    p_id = []  # percent identity
    aln_l = []  # alignment length
    positions = []  # start and stop positions in alignment

    old_id = ''
    s_id = ''  # subject ID
    n_s_id = 0  # count hits in DB
    count = 0

    evalue = 0.05

    infile = open(outPath + "blast.out", "r")

    for l in infile:
        l = l.strip()

        if l[0] != "#":
            l = l.split("\t")

            if (old_id != str(l[0])) and (old_id != ""):

                # calc average %ID, relative merged coverage and genomewide %ID:
                a_id = calc_a_id(p_id, aln_l)
                rel_mcov = calc_rel_mcov(positions, size[old_id])

                g_id = a_id * rel_mcov

                #save result:
                res[old_id] = str(round(g_id * 100, 3)) + "\t" + str(
                    round(rel_mcov * 100, 3)) + "\t" + str(n_s_id)

                # reset variables:
                p_id = []
                aln_l = []
                positions = []
                old_id = str(l[0])
                count = count + 1
                s_id = ''
                n_s_id = 0

            #check for evalue:
            if float(l[10]) <= evalue:
                # save output:
                if s_id != l[1]:
                    s_id = l[1]
                    n_s_id = n_s_id + 1

                p_id.append(float(l[2]))
                aln_l.append(int(l[3]))
                if int(l[6]) < int(l[7]):
                    positions.append((int(l[6]), int(l[7])))
                else:
                    positions.append((int(l[7]), int(l[6])))
                old_id = str(l[0])

    if (old_id != str(l[0])) and (old_id != ""):

        # calc average %ID, relative merged coverage and genomewide %ID:
        a_id = calc_a_id(p_id, aln_l)
        rel_mcov = calc_rel_mcov(positions, size[old_id])

        g_id = a_id * rel_mcov

        #save result:
        res[old_id] = str(round(g_id * 100, 3)) + "\t" + str(
            round(rel_mcov * 100, 3)) + "\t" + str(n_s_id)

    ################################################################################
    #   PRINT RESULTS
    ################################################################################

    print("preparing output...")

    outfile = open(outPath + "output.txt", "w")

    outfile.write(
        "#contigID\tclassification\tANI [%]\tmerged coverage [%]\tnumber of hits\tsize[bp]\n"
    )

    threshold = 1.7

    for i in contigID:

        if int(size[i]) < 500:
            outfile.write(
                i +
                "\tnot processed\tnot processed\tnot processed\tnot processed\t"
                + str(size[i]) + "\n")
        elif i in res:
            ani = float(res[i].split("\t")[0])
            if ani > threshold:
                outfile.write(i + "\tphage\t" + res[i] + "\t" + str(size[i]) +
                              "\n")
            else:
                outfile.write(i + "\tnegative\t" + res[i] + "\t" +
                              str(size[i]) + "\n")
        else:
            outfile.write(i + "\tnegative\t0\t0\t0\t" + str(size[i]) + "\n")
    outfile.close()

    # for wrapper:
    sys.stderr.write("DONE!")


# ----------------------------------------------------------------------------
if __name__ == "__main__":
    main()