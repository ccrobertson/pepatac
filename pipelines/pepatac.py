#!/usr/bin/env python
"""
PEPATAC - ATACseq pipeline
"""

__author__ = ["Jin Xu", "Nathan Sheffield", "Jason Smith"]
__email__ = "jasonsmith@virginia.edu"
__version__ = "0.8.9-dev"


from argparse import ArgumentParser
import os
import re
import sys
import tempfile
import pypiper
from pypiper import build_command
from refgenconf import RefGenConf as RGC, select_genome_config

TOOLS_FOLDER = "tools"
ANNO_FOLDER = "anno"
PEAK_CALLERS = ["fseq", "macs2"]
PEAK_TYPES = ["variable", "fixed"]
DEDUPLICATORS = ["picard", "samblaster"]
TRIMMERS = ["trimmomatic", "pyadapt", "skewer"]
BT2_IDX_KEY = "bowtie2_index"


def parse_arguments():
    """
    Parse command-line arguments passed to the pipeline.
    """
    # Argument Parsing from yaml file
    ###########################################################################
    parser = ArgumentParser(description='PEPATAC version ' + __version__)
    parser = pypiper.add_pypiper_args(parser, groups=
        ['pypiper', 'looper', 'ngs'],
        required=["input", "genome", "sample-name", "output-parent"])

    # Pipeline-specific arguments
    parser.add_argument("--peak-caller", dest="peak_caller",
                        default="macs2", choices=PEAK_CALLERS,
                        help="Name of peak caller")

    parser.add_argument("-gs", "--genome-size", default="hs", type=str,
                        help="MACS2 effective genome size. It can be 1.0e+9 "
                        "or 1000000000 or shortcuts:'hs' for human (2.7e9), "
                        "'mm' for mouse (1.87e9), 'ce' for C. elegans (9e7) "
                        "or 'dm' for fruitfly (1.2e8), Default:hs")

    parser.add_argument("--trimmer", dest="trimmer",
                        default="skewer", choices=TRIMMERS,
                        help="Name of read trimming program")

    parser.add_argument("--prealignments", default=[], type=str, nargs="+",
                        help="Space-delimited list of reference genomes to "
                             "align to before primary alignment.")

    parser.add_argument("--deduplicator", dest="deduplicator",
                        default="samblaster", choices=DEDUPLICATORS,
                        help="Name of deduplicator program")

    parser.add_argument("--TSS-name", default=None,
                        dest="TSS_name", type=str,
                        help="Path to TSS annotation file.")

    parser.add_argument("--blacklist", default=None,
                        dest="blacklist", type=str,
                        help="Path to genomic region blacklist file")

    parser.add_argument("--peak-type", default="variable",
                        dest="peak_type", choices=PEAK_TYPES, type=str,
                        help="Call variable or fixed width peaks.\n"
                             "Fixed width requires MACS2.")

    parser.add_argument("--extend", default=250,
                        dest="extend", type=int,
                        help="How far to extend fixed width peaks up and "
                             "downstream.")

    parser.add_argument("--frip-ref-peaks", default=None,
                        dest="frip_ref_peaks", type=str,
                        help="Path to reference peak set (BED format) for calculating FRiP")

    parser.add_argument("--motif", action='store_true',
                        dest="motif",
                        help="Perform motif enrichment analysis")

    parser.add_argument("--anno-name", default=None,
                        dest="anno_name", type=str,
                        help="Path to reference annotation file (BED format) for calculating FRiF")

    parser.add_argument("--prioritize", action='store_true', default=False,
                        dest="prioritize",
                        help="Plot cFRiF/FRiF using mutually exclusive priority"
                             " ranked features based on the order of feature"
                             " appearance in the feature annotation asset.")

    parser.add_argument("--keep", action='store_true',
                        dest="keep",
                        help="Enable this flag to keep prealignment BAM files")
                    
    parser.add_argument("--noFIFO", action='store_true',
                        dest="no_fifo",
                        help="Do NOT use named pipes during prealignments")

    parser.add_argument("--lite", dest="lite", action='store_true',
                        help="Only keep minimal, essential output to conserve "
                             "disk space.")

    parser.add_argument("-V", "--version", action="version",
                        version="%(prog)s {v}".format(v=__version__))

    args = parser.parse_args()

    # TODO: determine if it's safe to handle this requirement with argparse.
    # It may be that communication between pypiper and a pipeline via
    # the pipeline interface (and/or) looper, and how the partial argument
    # parsing is handled, that makes this more favorable.
    if not args.input:
        parser.print_help()
        raise SystemExit

    return args


def calc_frip(bamfile, peakfile, frip_func, pipeline_manager,
              aligned_reads_key="Aligned_reads"):
    """
    Calculate the fraction of reads in peaks (FRIP).

    Use the given function and data from an aligned reads file and a called
    peaks file, along with a PipelineManager, to calculate FRIP.

    :param str peakfile: path to called peaks file
    :param callable frip_func: how to calculate the fraction of reads in peaks;
        this must accept the path to the aligned reads file and the path to
        the called peaks file as arguments.
    :param str bamfile: path to aligned reads file
    :param pypiper.PipelineManager pipeline_manager: the PipelineManager in use
        for the pipeline calling this function
    :param str aligned_reads_key: name of the key from a stats (key-value) file
        to use to fetch the count of aligned reads
    :return float: fraction of reads in peaks
    """
    frip_cmd = frip_func(bamfile, peakfile)
    num_peak_reads = pipeline_manager.checkprint(frip_cmd)
    num_aligned_reads = pipeline_manager.get_stat(aligned_reads_key)
    print(num_aligned_reads, num_peak_reads)
    return float(num_peak_reads) / float(num_aligned_reads)


def _align_with_bt2(args, tools, paired, useFIFO, unmap_fq1, unmap_fq2,
                    assembly_identifier, assembly_bt2, outfolder,
                    aligndir=None, bt2_opts_txt=None):
    """
    A helper function to run alignments in series, so you can run one alignment
    followed by another; this is useful for successive decoy alignments.

    :param argparse.Namespace args: binding between option name and argument,
        e.g. from parsing command-line options
    :param looper.models.AttributeDict tools: binding between tool name and
        value, e.g. for tools/resources used by the pipeline
    :param bool paired: if True, use paired-end alignment
    :param bool useFIFO: if True, use named pipe instead of file creation
    :param str unmap_fq1: path to unmapped read1 FASTQ file
    :param str unmap_fq2: path to unmapped read2 FASTQ file
    :param str assembly_identifier: text identifying a genome assembly for the
        pipeline
    :param str assembly_bt2: assembly-specific bowtie2 folder (index, etc.)
    :param str outfolder: path to output directory for the pipeline
    :param str aligndir: name of folder for temporary output
    :param str bt2_opts_txt: command-line text for bowtie2 options
    :return (str, str): pair (R1, R2) of paths to FASTQ files
    """
    if os.path.exists(os.path.dirname(assembly_bt2)):
        pm.timestamp("### Map to " + assembly_identifier)
        if not aligndir:
            align_subdir = "aligned_{}_{}".format(args.genome_assembly,
                                                  assembly_identifier)
            sub_outdir = os.path.join(outfolder, align_subdir)
        else:
            sub_outdir = os.path.join(outfolder, aligndir)

        ngstk.make_dir(sub_outdir)
        bamname = "{}_{}.bam".format(args.sample_name, assembly_identifier)
        mapped_bam = os.path.join(sub_outdir, bamname)
        summary_name = "{}_{}_bt_aln_summary.log".format(args.sample_name,
                                                         assembly_identifier)
        summary_file = os.path.join(sub_outdir, summary_name)

        out_fastq_pre = os.path.join(
            sub_outdir, args.sample_name + "_" + assembly_identifier)

        out_fastq_r1    = out_fastq_pre + '_unmap_R1.fq'
        out_fastq_r1_gz = out_fastq_r1  + '.gz'

        out_fastq_r2    = out_fastq_pre + '_unmap_R2.fq'
        out_fastq_r2_gz = out_fastq_r2  + '.gz'

        if useFIFO and paired and not args.keep:
            out_fastq_tmp = os.path.join(sub_outdir,
                    assembly_identifier + "_bt2")
            cmd = "mkfifo " + out_fastq_tmp
            
            if os.path.exists(out_fastq_tmp):
                os.remove(out_fastq_tmp)
            pm.run(cmd, out_fastq_tmp)
        else:
            out_fastq_tmp    = out_fastq_pre + '_unmap.fq'
            out_fastq_tmp_gz = out_fastq_tmp + ".gz"

        filter_pair = build_command([tools.perl,
            tool_path("filter_paired_fq.pl"), out_fastq_tmp,
            unmap_fq1, unmap_fq2, out_fastq_r1, out_fastq_r2])
        # TODO: make filter_paired_fq work with SE data
        # cmd = build_command([tools.perl,
           # tool_path("filter_paired_fq.pl"), out_fastq_tmp,
           # unmap_fq1, out_fastq_r1])
        # For now, revert to old method

        if not bt2_opts_txt:
            # Default options
            bt2_opts_txt = "-k 1"  # Return only 1 alignment
            bt2_opts_txt += " -D 20 -R 3 -N 1 -L 20 -i S,1,0.50"

        # samtools sort needs a temporary directory
        tempdir = tempfile.mkdtemp(dir=sub_outdir)
        os.chmod(tempdir, 0o771)
        pm.clean_add(tempdir)  

        # Build bowtie2 command
        cmd = "(" + tools.bowtie2 + " -p " + str(pm.cores)
        cmd += " " + bt2_opts_txt
        cmd += " -x " + assembly_bt2
        cmd += " --rg-id " + args.sample_name
        cmd += " -U " + unmap_fq1
        cmd += " --un " + out_fastq_tmp
        if args.keep: #  or not paired
            #cmd += " --un-gz " + out_fastq_bt2 
            # Drop this for paired...repairing with filter_paired_fq.pl
            # In this samtools sort command we print to stdout and then use > to
            # redirect instead of  `+ " -o " + mapped_bam` because then samtools
            # uses a random temp file, so it won't choke if the job gets
            # interrupted and restarted at this step.
            cmd += " | " + tools.samtools + " view -bS - -@ 1"  # convert to bam
            cmd += " | " + tools.samtools + " sort - -@ 1"      # sort output
            cmd += " -T " + tempdir
            cmd += " -o " + mapped_bam
        else:
            cmd += " > /dev/null"
        cmd += ") 2>" + summary_file

        if paired:
            if args.keep or not useFIFO:
                pm.run([cmd, filter_pair], mapped_bam)
            else:
                pm.wait = False
                pm.run(filter_pair, [summary_file, out_fastq_r2_gz],
                       container=pm.container)
                pm.wait = True
                pm.run(cmd, [summary_file, out_fastq_r2_gz],
                       container=pm.container)
        else:
            if args.keep:
                pm.run(cmd, mapped_bam)
            else:
                # TODO: switch to this once filter_paired_fq works with SE
                #pm.run(cmd2, summary_file)
                #pm.run(cmd1, out_fastq_r1)
                pm.run(cmd, out_fastq_tmp_gz,
                       container=pm.container)

        pm.clean_add(out_fastq_tmp)

        # get aligned read counts
        #if args.keep and paired:
        #    cmd = ("grep 'aligned concordantly exactly 1 time' " +
        #           summary_file + " | awk '{print $1}'")
        #else:
        cmd = ("grep 'aligned exactly 1 time' " + summary_file +
               " | awk '{print $1}'")
        align_exact = pm.checkprint(cmd)
        if align_exact:
            ar = float(align_exact)*2
        else:
            ar = 0

        # report aligned reads
        pm.report_result("Aligned_reads_" + assembly_identifier, ar)
        try:
            # wrapped in try block in case Trimmed_reads is not reported in this
            # pipeline.
            tr = float(pm.get_stat("Trimmed_reads"))
        except:
            print("Trimmed reads is not reported.")
        else:
            res_key = "Alignment_rate_" + assembly_identifier
            pm.report_result(res_key, round(float(ar) * 100 / float(tr), 2))
        
        if paired:
            unmap_fq1 = out_fastq_r1
            unmap_fq2 = out_fastq_r2
        else:
            # Use alternate once filter_paired_fq is working with SE
            #unmap_fq1 = out_fastq_r1
            unmap_fq1 = out_fastq_tmp
            unmap_fq2 = ""

        return unmap_fq1, unmap_fq2
    else:
        msg = "No {} index found in {}; skipping.".format(
            assembly_identifier, os.path.dirname(assembly_bt2))
        print(msg)
        return unmap_fq1, unmap_fq2


def tool_path(tool_name):
    """
    Return the path to a tool used by this pipeline.

    :param str tool_name: name of the tool (e.g., a script filename)
    :return str: real, absolute path to tool (expansion and symlink resolution)
    """

    return os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        TOOLS_FOLDER, tool_name)


def check_commands(commands, ignore=''):
    """
    Check if command(s) can be called

    :param attributedict commands: dictionary of commands to check
    :param list ignore: list of commands that are optional and can be ignored
    """

    # Use `command` to see if command is callable, store exit code
    is_callable = True
    uncallable = []
    for name, command in commands.items():
        if command not in ignore:
            # if an environment variable is not expanded it means it points to
            # an uncallable command
            if '$' in command:
                # try to expand
                command = os.path.expandvars(os.path.expanduser(command))
                if not os.path.exists(command):
                    uncallable.append(command)

            # if a command is a java file, modify the command
            if '.jar' in command:
                command = "java -jar " + command

            code = os.system("command -v {0} >/dev/null 2>&1 || {{ exit 1; }}".format(command))
            # If exit code is not 0, track which command failed
            #print("{} code {}".format(command, code))  # DEBUG
            if code != 0:
                uncallable.append(command)
                is_callable = False
    if is_callable:
        return True
    else:
        print("The following required tool(s) are not callable: {0}".format(' '.join(uncallable)))
        return False


def _add_resources(args, res, asset_dict=None):
    """
    Add additional resources needed for pipeline.

    :param argparse.Namespace args: binding between option name and argument,
        e.g. from parsing command-line options
    :param pm.config.resources res: pipeline manager resources list
    :param asset_dict list: list of dictionary of assets to add
    """

    rgc = RGC(select_genome_config(res.get("genome_config")))

    key_errors = []
    exist_errors = []
    required_list = []

    # Check that bowtie2 indicies exist for specified prealignments
    for reference in args.prealignments:
        for asset in [BT2_IDX_KEY]:
            try:
                res[asset] = rgc.get_asset(reference, asset)
            except KeyError:
                err_msg = "{} for {} is missing from REFGENIE config file."
                pm.fail_pipeline(KeyError(err_msg.format(asset, reference)))
            except:
                err_msg = "{} for {} does not exist."
                pm.fail_pipeline(IOError(err_msg.format(asset, reference)))

    # Check specified assets
    if not asset_dict:
        return res, rgc
    else:
        for item in asset_dict:
            pm.debug("item: {}".format(item))  # DEBUG
            asset = item["asset_name"]
            seek_key = item["seek_key"] or item["asset_name"]
            tag = item["tag_name"] or "default"
            arg = item["arg"]
            user_arg = item["user_arg"]
            req = item["required"]

            if arg and hasattr(args, arg) and getattr(args, arg):
                res[seek_key] = os.path.abspath(getattr(args, arg))
            else:
                try:
                    pm.debug("{} - {}.{}:{}".format(args.genome_assembly,
                                                    asset,
                                                    seek_key,
                                                    tag))  # DEBUG
                    res[seek_key] = rgc.get_asset(args.genome_assembly,
                                                  asset_name=str(asset),
                                                  tag_name=str(tag),
                                                  seek_key=str(seek_key))
                except KeyError:
                    key_errors.append(item)
                    if req:
                        required_list.append(item)
                except:
                    exist_errors.append(item)
                    if req:
                        required_list.append(item)

        if len(key_errors) > 0 or len(exist_errors) > 0:
            pm.info("Some assets are not found. You can update your REFGENIE "
                    "config file or point directly to the file using the noted "
                    "command-line arguments:")

        if len(key_errors) > 0:
            if required_list:
                err_msg = "Required assets missing from REFGENIE config file: {}"
                pm.fail_pipeline(IOError(err_msg.format(", ".join(["{asset_name}.{seek_key}:{tag_name}".format(**x) for x in required_list]))))
            else:
                warning_msg = "Optional assets missing from REFGENIE config file: {}"
                pm.info(warning_msg.format(", ".join(["{asset_name}.{seek_key}:{tag_name}".format(**x) for x in key_errors])))

        if len(exist_errors) > 0:
            if required_list:
                err_msg = "Required assets not existing: {}"
                pm.fail_pipeline(IOError(err_msg.format(", ".join(["{asset_name}.{seek_key}:{tag_name} (--{user_arg})".format(**x) for x in required_list]))))
            else:
                warning_msg = "Optional assets not existing: {}"
                pm.info(warning_msg.format(", ".join(["{asset_name}.{seek_key}:{tag_name} (--{user_arg})".format(**x) for x in exist_errors])))

        return res, rgc


################################################################################
#                                 Pipeline MAIN                                #
################################################################################
def main():
    """
    Main pipeline process.
    """

    args = parse_arguments()

    args.paired_end = args.single_or_paired == "paired"

    # Initialize, creating global PipelineManager and NGSTk instance for
    # access in ancillary functions outside of main().
    outfolder = os.path.abspath(
        os.path.join(args.output_parent, args.sample_name))
    global pm
    pm = pypiper.PipelineManager(
        name="PEPATAC", outfolder=outfolder, args=args, version=__version__)
    global ngstk
    ngstk = pypiper.NGSTk(pm=pm)

    # Convenience alias
    tools = pm.config.tools
    param = pm.config.parameters
    res = pm.config.resources

    # Check that the required tools are callable by the pipeline
    opt_tools = ["fseq", "${PICARD}", "${TRIMMOMATIC}", "pyadapt",
                 "findMotifsGenome.pl"]

    # If using optional tools, remove those from the skipped checks
    if args.trimmer == "trimmomatic":
        if 'trimmomatic' in opt_tools: opt_tools.remove('trimmomatic')

    if args.trimmer == "pyadapt":
        if 'pyadapt' in opt_tools: opt_tools.remove('pyadapt')

    if args.deduplicator == "picard":
        if '${PICARD}' in opt_tools: opt_tools.remove('${PICARD}')

    if args.peak_caller == "fseq":
        if 'fseq' in opt_tools: opt_tools.remove('fseq')

    if args.motif:
        if 'findMotifsGenome.pl' in opt_tools: opt_tools.remove('findMotifsGenome.pl')

    # Confirm required tools are all callable
    if not check_commands(tools, opt_tools):
        err_msg = "Missing required tools. See message above."
        pm.fail_pipeline(RuntimeError(err_msg))

    if args.input2 and not args.paired_end:
        err_msg = "Incompatible settings: You specified single-end, but provided --input2."
        pm.fail_pipeline(RuntimeError(err_msg))

    # Set up reference resource according to genome prefix.
    check_list = [
        {"asset_name":"fasta", "seek_key":"chrom_sizes",
         "tag_name":"default", "arg":None, "user_arg":None,
         "required":True},
        {"asset_name":"fasta", "seek_key":None,
         "tag_name":"default", "arg":None, "user_arg":None,
         "required":True},
        {"asset_name":BT2_IDX_KEY, "seek_key":None,
         "tag_name":"default", "arg":None, "user_arg":None,
         "required":True}
    ]
    # If user specifies TSS file, use that instead of the refgenie asset
    if not (args.TSS_name):
        check_list.append(
            {"asset_name":"refgene_anno", "seek_key":"refgene_tss",
             "tag_name":"default", "arg":"TSS_name", "user_arg":"TSS-name",
             "required":False}
        )
    # If user specifies feature annotation file,
    # use that instead of the refgenie managed asset
    if not (args.anno_name):
        check_list.append(
            {"asset_name":"feat_annotation", "seek_key":"feat_annotation",
            "tag_name":"default", "arg":"anno_name", "user_arg":"anno-name",
            "required":False}
        )
    # If user specifies blacklist file,
    # use that instead of the refgenie managed asset
    if not (args.blacklist):
        check_list.append(
            {"asset_name":"blacklist", "seek_key":"blacklist",
            "tag_name":"default", "arg":"blacklist", "user_arg":"blacklist",
            "required":False}
        )
    res, rgc = _add_resources(args, res, check_list)

    # If the user specifies optional files, add those to our resources
    if ((args.blacklist) and os.path.isfile(args.blacklist) and
            os.stat(args.blacklist).st_size > 0):
        res.blacklist = args.blacklist
    if ((args.frip_ref_peaks) and os.path.isfile(args.frip_ref_peaks) and
            os.stat(args.frip_ref_peaks).st_size > 0):
        res.frip_ref_peaks = args.frip_ref_peaks
    if ((args.TSS_name) and os.path.isfile(args.TSS_name) and
            os.stat(args.TSS_name).st_size > 0):
        res.TSS_name = args.TSS_name
    if ((args.anno_name) and os.path.isfile(args.anno_name) and
            os.stat(args.anno_name).st_size > 0):
        res.feat_annotation = args.anno_name

    # Adapter file can be set in the config; if left null, we use a default.
    res.adapters = res.adapters or tool_path("NexteraPE-PE.fa")

    param.outfolder = outfolder

    # Check that the input file(s) exist before continuing
    if os.path.isfile(args.input[0]) and os.stat(args.input[0]).st_size > 0:
        print("Local input file: " + args.input[0])
    elif os.path.isfile(args.input[0]) and os.stat(args.input[0]).st_size == 0:
        # The read1 file exists but is empty
        err_msg = "File exists but is empty: {}"
        pm.fail_pipeline(IOError(err_msg.format(args.input[0])))
    else:
        # The read1 file does not exist
        err_msg = "Could not find: {}"
        pm.fail_pipeline(IOError(err_msg.format(args.input[0])))

    if args.input2:
        if (os.path.isfile(args.input2[0]) and
                os.stat(args.input2[0]).st_size > 0):
            print("Local input file: " + args.input2[0])
        elif (os.path.isfile(args.input2[0]) and
                os.stat(args.input2[0]).st_size == 0):
            # The read1 file exists but is empty
            err_msg = "File exists but is empty: {}"
            pm.fail_pipeline(IOError(err_msg.format(args.input2[0])))
        else:
            # The read1 file does not exist
            err_msg = "Could not find: {}"
            pm.fail_pipeline(IOError(err_msg.format(args.input2[0])))

    container = None

    ###########################################################################

    pm.report_result(
        "File_mb",
        round(ngstk.get_file_size(
              [x for x in [args.input, args.input2] if x is not None])), 2)
    pm.report_result("Read_type", args.single_or_paired)
    pm.report_result("Genome", args.genome_assembly)

    # ATACseq pipeline
    # Each (major) step should have its own subfolder
    raw_folder = os.path.join(param.outfolder, "raw")
    fastq_folder = os.path.join(param.outfolder, "fastq")

    pm.timestamp("### Merge/link and fastq conversion: ")
    # This command will merge multiple inputs so you can use multiple
    # sequencing lanes in a single pipeline run.
    local_input_files = ngstk.merge_or_link(
        [args.input, args.input2], raw_folder, args.sample_name)
    cmd, out_fastq_pre, unaligned_fastq = ngstk.input_to_fastq(
        local_input_files, args.sample_name, args.paired_end, fastq_folder,
        zipmode=True)
    print(cmd)
    pm.run(cmd, unaligned_fastq,
           follow=ngstk.check_fastq(
               local_input_files, unaligned_fastq, args.paired_end),
           container=pm.container)
    pm.clean_add(out_fastq_pre + "*.fastq", conditional=True)

    if args.paired_end:
        untrimmed_fastq1 = unaligned_fastq[0]
        untrimmed_fastq2 = unaligned_fastq[1]
    else:
        untrimmed_fastq1 = unaligned_fastq
        untrimmed_fastq2 = None

    # Prepare alignment output folder
    map_genome_folder = os.path.join(param.outfolder,
                                     "aligned_" + args.genome_assembly)
    ngstk.make_dir(map_genome_folder)
    rmdup_bam = os.path.join(map_genome_folder,
                             args.sample_name + "_sort_dedup.bam")

    ############################################################################
    #                          Begin adapter trimming                          #
    ############################################################################
    pm.timestamp("### Adapter trimming: ")

    # Create names for trimmed FASTQ files.
    if args.trimmer == "trimmomatic":
        trimming_prefix = os.path.join(fastq_folder, args.sample_name)
    else:
        trimming_prefix = out_fastq_pre
    trimmed_fastq = trimming_prefix + "_R1_trim.fastq"
    trimmed_fastq_R2 = trimming_prefix + "_R2_trim.fastq"

    # Create trimming command(s).
    if args.trimmer == "pyadapt":
        if not args.paired_end:
            raise NotImplementedError(
                "pyadapt trimming requires paired-end reads.")
        # TODO: make pyadapt give options for output file name.
        trim_cmd_chunks = [
            tool_path("pyadapter_trim.py"),
            ("-a", untrimmed_fastq1),
            ("-b", untrimmed_fastq2),
            ("-o", out_fastq_pre),
            "-u"
        ]
        cmd = build_command(trim_cmd_chunks)

    elif args.trimmer == "skewer":
        # Create the primary skewer command.
        # Don't compress output at this stage, because the pre-alignment mechanism
        # requires unzipped fastq.
        trim_cmd_chunks = [
            tools.skewer,  # + " --quiet"
            ("-f", "sanger"),
            ("-t", str(args.cores)),
            ("-m", "pe" if args.paired_end else "any"),
            ("-x", res.adapters),
            # "-z",  # compress output
            "--quiet",
            ("-o", out_fastq_pre),
            untrimmed_fastq1,
            untrimmed_fastq2 if args.paired_end else None
        ]
        trimming_command = build_command(trim_cmd_chunks)

        # Create the skewer file renaming commands.
        if args.paired_end:
            skewer_filename_pairs = \
                [("{}-trimmed-pair1.fastq".format(out_fastq_pre),
                 trimmed_fastq)]
            skewer_filename_pairs.append(
                ("{}-trimmed-pair2.fastq".format(out_fastq_pre),
                 trimmed_fastq_R2))
        else:
            skewer_filename_pairs = \
                [("{}-trimmed.fastq".format(out_fastq_pre), trimmed_fastq)]

        trimming_renaming_commands = [build_command(["mv", old, new])
                                      for old, new in skewer_filename_pairs]
        # Rename the logfile.
        # skewer_filename_pairs.append(
        #    ("{}-trimmed.log".format(out_fastq_pre), trimLog))

        # Pypiper submits the commands serially.
        cmd = [trimming_command] + trimming_renaming_commands

    else:
        # Default to trimmomatic.
        trim_cmd_chunks = [
            "{java} -Xmx{mem} -jar {trim} {PE} -threads {cores}".format(
                java=tools.java, mem=pm.mem,
                trim=tools.trimmomatic,
                PE="PE" if args.paired_end else "",
                cores=pm.cores),
            local_input_files[0],
            local_input_files[1],
            trimmed_fastq,
            trimming_prefix + "_R1_unpaired.fq",
            trimmed_fastq_R2 if args.paired_end else "",
            trimming_prefix + "_R2_unpaired.fq" if args.paired_end else "",
            "ILLUMINACLIP:" + res.adapters + ":2:30:10"
        ]
        cmd = build_command(trim_cmd_chunks)

    if not os.path.exists(rmdup_bam) or args.new_start:
        pm.run(cmd, trimmed_fastq,
               follow=ngstk.check_trim(
                   trimmed_fastq, args.paired_end, trimmed_fastq_R2,
                   fastqc_folder=os.path.join(param.outfolder, "fastqc")))

    pm.clean_add(os.path.join(fastq_folder, "*.fastq"), conditional=True)
    pm.clean_add(os.path.join(fastq_folder, "*.log"), conditional=True)

    # Prepare variables for alignment step
    unmap_fq1 = trimmed_fastq
    unmap_fq2 = trimmed_fastq_R2

    ############################################################################
    #                    Map to any requested prealignments                    #
    ############################################################################

    # We recommend mapping to chrM (i.e. rCRSd) before primary genome alignment
    pm.timestamp("### Prealignments")
    # Keep track of the unmapped files in order to compress them after final
    # alignment.
    to_compress = []
    if len(args.prealignments) == 0:
        print("You may use `--prealignments` to align to references before "
              "the genome alignment step. See docs.")
    else:
        print("Prealignment assemblies: " + str(args.prealignments))
        # Loop through any prealignment references and map to them sequentially
        for reference in args.prealignments:
            if args.no_fifo:
                unmap_fq1, unmap_fq2 = _align_with_bt2(
                    args, tools, args.paired_end, False,
                    unmap_fq1, unmap_fq2, reference,
                    assembly_bt2=os.path.join(
                        rgc.get_asset(reference, BT2_IDX_KEY), reference),
                    outfolder=param.outfolder, aligndir="prealignments",
                    bt2_opts_txt=param.bowtie2_pre.params)
                to_compress.append(unmap_fq1)
                if args.paired_end:
                    to_compress.append(unmap_fq2)
            else:
                unmap_fq1, unmap_fq2 = _align_with_bt2(
                    args, tools, args.paired_end, True,
                    unmap_fq1, unmap_fq2, reference,
                    assembly_bt2=os.path.join(
                        rgc.get_asset(reference, BT2_IDX_KEY), reference), 
                    outfolder=param.outfolder, aligndir="prealignments",
                    bt2_opts_txt=param.bowtie2_pre.params)
                to_compress.append(unmap_fq1)
                if args.paired_end:
                    to_compress.append(unmap_fq2)

    pm.timestamp("### Compress all unmapped read files")
    for unmapped_fq in to_compress:
        # Compress unmapped fastq reads
        if not pypiper.is_gzipped_fastq(unmapped_fq) and not unmapped_fq == '':
            if os.path.exists(unmapped_fq):
                cmd = (ngstk.ziptool + " " + unmapped_fq)
                unmapped_fq = unmapped_fq + ".gz"
                pm.run(cmd, unmapped_fq)

    ############################################################################
    #                           Map to primary genome                          #
    ############################################################################

    pm.timestamp("### Map to genome")
    mapping_genome_bam = os.path.join(
        map_genome_folder, args.sample_name + "_sort.bam")
    mapping_genome_bam_temp = os.path.join(
        map_genome_folder, args.sample_name + "_temp.bam")
    failQC_genome_bam = os.path.join(
        map_genome_folder, args.sample_name + "_fail_qc.bam")
    unmap_genome_bam = os.path.join(
        map_genome_folder, args.sample_name + "_unmap.bam")

    if not param.bowtie2.params:
        bt2_options = " --very-sensitive"
        if args.paired_end:
            bt2_options += " -X 2000"
    else:
        bt2_options = param.bowtie2.params

    # samtools sort needs a temporary directory
    tempdir = tempfile.mkdtemp(dir=map_genome_folder)
    os.chmod(tempdir, 0o771)
    pm.clean_add(tempdir)

    unmap_fq1 = unmap_fq1 + ".gz"
    unmap_fq2 = unmap_fq2 + ".gz"

    cmd = tools.bowtie2 + " -p " + str(pm.cores)
    cmd += " " + bt2_options
    cmd += " --rg-id " + args.sample_name
    cmd += " -x " + os.path.join(
        rgc.get_asset(args.genome_assembly, BT2_IDX_KEY),
                      args.genome_assembly)
    if args.paired_end:
        cmd += " -1 " + unmap_fq1 + " -2 " + unmap_fq2
    else:
        cmd += " -U " + unmap_fq1
    cmd += " | " + tools.samtools + " view -bS - -@ 1 "
    cmd += " | " + tools.samtools + " sort - -@ 1"
    cmd += " -T " + tempdir
    cmd += " -o " + mapping_genome_bam_temp

    # Split genome mapping result bamfile into two: high-quality aligned
    # reads (keepers) and unmapped reads (in case we want to analyze the
    # altogether unmapped reads)
    # Default (samtools.params): skip alignments with MAPQ less than 10 (-q 10)
    cmd2 = (tools.samtools + " view -b " + param.samtools.params + " -@ " +
            str(pm.cores) + " -U " + failQC_genome_bam + " ")
    if args.paired_end:
        # add a step to accept only reads mapped in proper pair
        cmd2 += "-f 2 "

    cmd2 += mapping_genome_bam_temp + " > " + mapping_genome_bam

    def check_alignment_genome():
        mr = ngstk.count_mapped_reads(mapping_genome_bam_temp, args.paired_end)
        ar = ngstk.count_mapped_reads(mapping_genome_bam, args.paired_end)
        rr = float(pm.get_stat("Raw_reads"))
        tr = float(pm.get_stat("Trimmed_reads"))
        pm.report_result("Mapped_reads", mr)
        pm.report_result("QC_filtered_reads",
                         round(float(mr)) - round(float(ar)))
        pm.report_result("Aligned_reads", ar)
        pm.report_result("Alignment_rate", round(float(ar) * 100 /
                         float(tr), 2))
        pm.report_result("Total_efficiency", round(float(ar) * 100 /
                         float(rr), 2))

    pm.run([cmd, cmd2], mapping_genome_bam,
           follow=check_alignment_genome)

    # Index the temporary bam file and the sorted bam file
    temp_mapping_index   = os.path.join(mapping_genome_bam_temp + ".bai")
    mapping_genome_index = os.path.join(mapping_genome_bam + ".bai")
    cmd1 = tools.samtools + " index " + mapping_genome_bam_temp
    cmd2 = tools.samtools + " index " + mapping_genome_bam
    pm.run([cmd1, cmd2], mapping_genome_index)
    pm.clean_add(temp_mapping_index)

    # If first run, use the temp bam file
    if os.path.isfile(mapping_genome_bam_temp) and os.stat(mapping_genome_bam_temp).st_size > 0:
        bam_file = mapping_genome_bam_temp
    # Otherwise, use the final bam file previously generated
    else:
        bam_file = mapping_genome_bam

    # Determine mitochondrial read counts
    mito_name = ["chrM", "chrMT", "M", "MT", "rCRSd"]

    if pm.get_stat("Mitochondrial_reads") is None:
        cmd = (tools.samtools + " idxstats " + bam_file + " | grep")
        for name in mito_name:
            cmd += " -we '" + name + "'"
        cmd += "| cut -f 3"
        mr = pm.checkprint(cmd)

        # If there are mitochondrial reads, report and remove them
        if mr and float(mr.strip()) != 0:
            pm.report_result("Mitochondrial_reads", round(float(mr)))
            noMT_mapping_genome_bam = os.path.join(
                map_genome_folder, args.sample_name + "_noMT.bam")
            cmd1 = (tools.samtools + " idxstats " + mapping_genome_bam +
                    " | cut -f 1 | grep")
            for name in mito_name:
                cmd1 += " -vwe '" + name + "'"
            cmd1 += ("| xargs " + tools.samtools + " view -b -@ " +
                     str(pm.cores) + " " + mapping_genome_bam + " > " +
                     noMT_mapping_genome_bam)
            cmd2 = ("mv " + noMT_mapping_genome_bam + " " + mapping_genome_bam)
            # Reindex the sorted bam file now that mito reads are removed
            cmd3 = tools.samtools + " index " + mapping_genome_bam
            pm.run([cmd1, cmd2, cmd3], noMT_mapping_genome_bam,
                   container=pm.container)
        else:
            pm.report_result("Mitochondrial_reads", 0)

    ############################################################################
    #         Calculate quality control metrics for the alignment file         #
    ############################################################################

    pm.timestamp("### Calculate NRF, PBC1, and PBC2")
    QC_folder = os.path.join(param.outfolder, "QC_" + args.genome_assembly)
    ngstk.make_dir(QC_folder)

    bamQC = os.path.join(QC_folder, args.sample_name + "_bamQC.tsv")
    cmd = tool_path("bamQC.py")
    cmd += " -i " + mapping_genome_bam
    cmd += " -c " + str(pm.cores)
    cmd += " -o " + bamQC

    def report_bam_qc(bamqc_log):
        # Reported BAM QC metrics via the bamQC metrics file
        if os.path.isfile(bamqc_log):
            cmd1 = ("awk '{ for (i=1; i<=NF; ++i) {" +
                    " if ($i ~ \"NRF\") c=i } getline; print $c }' " +
                    bamqc_log)
            cmd2 = ("awk '{ for (i=1; i<=NF; ++i) {" +
                    " if ($i ~ \"PBC1\") c=i } getline; print $c }' " +
                    bamqc_log)
            cmd3 = ("awk '{ for (i=1; i<=NF; ++i) {" +
                    " if ($i ~ \"PBC2\") c=i } getline; print $c }' " +
                    bamqc_log)
            nrf = pm.checkprint(cmd1)
            pbc1 = pm.checkprint(cmd2)
            pbc2 = pm.checkprint(cmd3)
        else:
            # there were no successful chromosomes yielding results
            nrf = 0
            pbc1 = 0
            pbc2 = 0

        pm.report_result("NRF", round(float(nrf),2))
        pm.report_result("PBC1", round(float(pbc1),2))
        pm.report_result("PBC2", round(float(pbc2), 2))

    pm.run(cmd, bamQC, follow=lambda: report_bam_qc(bamQC),
           container=pm.container)

    # Now produce the unmapped file
    def count_unmapped_reads():
        # Report total number of unmapped reads (-f 4)
        cmd = (tools.samtools + " view -c -f 4 -@ " + str(pm.cores) +
               " " + mapping_genome_bam_temp)
        ur = pm.checkprint(cmd)
        pm.report_result("Unmapped_reads", round(float(ur)))

    unmap_cmd = tools.samtools + " view -b -@ " + str(pm.cores)
    if args.paired_end:
        # require both read and mate unmapped
        unmap_cmd += " -f 12 "
    else:
        # require only read unmapped
        unmap_cmd += " -f 4 "

    unmap_cmd += " " + mapping_genome_bam_temp + " > " + unmap_genome_bam
    pm.run(unmap_cmd, unmap_genome_bam, follow=count_unmapped_reads,
           container=pm.container)

    # Remove temporary bam file from unmapped file production
    pm.clean_add(mapping_genome_bam_temp)

    pm.timestamp("### Remove duplicates and produce signal tracks")

    def estimate_lib_size(dedup_log):
        # In millions of reads; contributed by Ryan
        # NOTE: from Picard manual: without optical duplicate counts,
        #       library size estimation will be inaccurate.
        cmd = ("awk -F'\t' -f " + tool_path("extract_picard_lib.awk") +
               " " + dedup_log)
        picard_est_lib_size = pm.checkprint(cmd)
        pm.report_result("Picard_est_lib_size", picard_est_lib_size)

    def post_dup_aligned_reads(dedup_log):
        if args.deduplicator == "picard":
            # Number of aligned reads post tools.picard REMOVE_DUPLICATES
            cmd = ("awk -F'\t' -f " +
                   tool_path("extract_post_dup_aligned_reads.awk") + " " +
                   dedup_log)            
        elif args.deduplicator == "samblaster":
            cmd = ("grep 'Removed' " + dedup_log + " | cut -f 3 -d ' '")
        else:
            cmd = ("grep 'Removed' " + dedup_log + " | cut -f 3 -d ' '")

        pdar = pm.checkprint(cmd)
        ar = float(pm.get_stat("Aligned_reads"))
        rr = float(pm.get_stat("Raw_reads"))
        tr = float(pm.get_stat("Trimmed_reads"))

        if not pdar and not pdar.strip():
            pdar = ar

        if args.deduplicator == "samblaster":
            dr = pdar
            pdar = float(ar) - float(dr)
            dar = round(float(pdar) * 100 / float(tr), 2)
            dte = round(float(pdar) * 100 / float(rr), 2)
        elif args.deduplicator == "picard":
            dr = float(ar) - float(pdar)
            dar = round(float(pdar) * 100 / float(tr), 2)
            dte = round(float(pdar) * 100 / float(rr), 2)
        else:
            dr = pdar
            pdar = float(ar) - float(dr)
            dar = round(float(pdar) * 100 / float(tr), 2)
            dte = round(float(pdar) * 100 / float(rr), 2)

        pm.report_result("Duplicate_reads", dr)
        pm.report_result("Dedup_aligned_reads", pdar)
        pm.report_result("Dedup_alignment_rate", dar)
        pm.report_result("Dedup_total_efficiency", dte)

    metrics_file = os.path.join(
        map_genome_folder, args.sample_name + "_dedup_metrics_bam.txt")
    dedup_log = os.path.join(
        map_genome_folder, args.sample_name + "_dedup_metrics_log.txt")

    # samtools sort needs a temporary directory
    tempdir = tempfile.mkdtemp(dir=map_genome_folder)
    os.chmod(tempdir, 0o771)
    pm.clean_add(tempdir)

    if args.deduplicator == "picard":
        cmd1 = (tools.java + " -Xmx" + str(pm.javamem) + " -jar " + 
                tools.picard + " MarkDuplicates")
        cmd1 += " INPUT=" + mapping_genome_bam
        cmd1 += " OUTPUT=" + rmdup_bam
        cmd1 += " METRICS_FILE=" + metrics_file
        cmd1 += " VALIDATION_STRINGENCY=LENIENT"
        cmd1 += " ASSUME_SORTED=true REMOVE_DUPLICATES=true > " + dedup_log
        cmd2 = tools.samtools + " index " + rmdup_bam
    elif args.deduplicator == "samblaster":
        nProc = max(int(pm.cores / 4), 1)
        samblaster_cmd_chunks = [
            "{} sort -n -@ {}".format(tools.samtools, str(nProc)),
            ("-T", tempdir),
            mapping_genome_bam,
            "|",
            "{} view -h - -@ {}".format(tools.samtools, str(nProc)),
            "|",
            "{} -r 2> {}".format(tools.samblaster, dedup_log),
            "|",
            "{} view -b - -@ {}".format(tools.samtools, str(nProc)),
            "|",
            "{} sort - -@ {}".format(tools.samtools, str(nProc)),
            ("-T", tempdir),
            ("-o", rmdup_bam)
        ]
        cmd1 = build_command(samblaster_cmd_chunks)
        cmd2 = tools.samtools + " index " + rmdup_bam
        # no separate metrics file with samblaster
        metrics_file = dedup_log
    else:
        pm.info("PEPATAC could not determine a valid deduplicator tool")
        pm.stop_pipeline()

    pm.run([cmd1, cmd2], rmdup_bam,
           follow=lambda: post_dup_aligned_reads(metrics_file),
           container=pm.container)

    ############################################################################
    #                         Produce signal tracks                            #
    ############################################################################
    # "Exact cuts" are nucleotide-resolution tracks of exact bases
    # where the transposition (or DNAse cut) happened;
    # In the past I used wigToBigWig on a combined wig file, but this ends up
    # using a boatload of memory (more than 32GB); in contrast, running the
    # wig -> bw conversion on each chrom and then combining them with bigWigCat
    # requires much less memory. This was a memory bottleneck in the pipeline.

    pm.timestamp("### Produce smoothed and nucleotide-resolution tracks")

    exact_folder = os.path.join(map_genome_folder + "_exact")
    temp_exact_folder = os.path.join(exact_folder, "temp")
    ngstk.make_dir(exact_folder)
    ngstk.make_dir(temp_exact_folder)
    exact_target = os.path.join(exact_folder, args.sample_name + "_exact.bw")
    smooth_target = os.path.join(map_genome_folder,
                                 args.sample_name + "_smooth.bw")
    shift_bed = os.path.join(exact_folder, args.sample_name + "_shift.bed")

    cmd = tool_path("bamSitesToWig.py")
    cmd += " -i " + rmdup_bam
    cmd += " -c " + res.chrom_sizes
    cmd += " -b " + shift_bed # request bed output
    cmd += " -o " + exact_target
    cmd += " -w " + smooth_target
    cmd += " -m " + "atac"
    cmd += " -p " + str(int(max(1, int(pm.cores) * 2/3)))
    pm.run(cmd, exact_target)
    pm.clean_add(temp_exact_folder)

    ############################################################################
    #                          Determine TSS enrichment                        #
    ############################################################################

    if not os.path.exists(res.refgene_tss):
        print("Skipping TSS -- TSS enrichment requires TSS annotation file: {}"
              .format(res.refgene_tss))
    else:
        pm.timestamp("### Calculate TSS enrichment")

        Tss_enrich = os.path.join(QC_folder, args.sample_name +
                                  "_TSS_enrichment.txt")
        cmd = tool_path("pyTssEnrichment.py")
        cmd += " -a " + rmdup_bam + " -b " + res.refgene_tss + " -p ends"
        cmd += " -c " + str(pm.cores)
        cmd += " -z -v -s 6 -o " + Tss_enrich
        pm.run(cmd, Tss_enrich, nofail=True)

        if not pm.get_stat('TSS_score') or args.new_start:
            with open(Tss_enrich) as f:
                floats = list(map(float, f))
            try:
                # If the TSS enrichment is 0, don't report
                list_len = 0.05*float(len(floats))
                normTSS = [x / (sum(floats[1:int(list_len)]) /
                           len(floats[1:int(list_len)])) for x in floats]
                max_index = normTSS.index(max(normTSS))

                if (((normTSS[max_index]/normTSS[max_index-1]) > 1.5) and
                    ((normTSS[max_index]/normTSS[max_index+1]) > 1.5)):
                    tmpTSS = list(normTSS)
                    del tmpTSS[max_index]
                    max_index = tmpTSS.index(max(tmpTSS)) + 1

                Tss_score = round(
                    (sum(normTSS[int(max_index-50):int(max_index+50)])) /
                    (len(normTSS[int(max_index-50):int(max_index+50)])), 1)

                pm.report_result("TSS_score", round(Tss_score, 1))
            except ZeroDivisionError:
                pass
        
        # Call Rscript to plot TSS Enrichment
        Tss_pdf = os.path.join(QC_folder,  args.sample_name +
                               "_TSS_enrichment.pdf")
        Tss_png = os.path.join(QC_folder,  args.sample_name +
                               "_TSS_enrichment.png")
        cmd = (tools.Rscript + " " + tool_path("PEPATAC.R") + 
               " tss -i " + Tss_enrich)
        pm.run(cmd, Tss_pdf, nofail=True)

        pm.report_object("TSS enrichment", Tss_pdf, anchor_image=Tss_png)

    ############################################################################
    #                         Fragment distribution                            #
    ############################################################################
    if args.paired_end:
        pm.timestamp("### Plot fragment distribution")
        frag_len = os.path.join(QC_folder,
                                args.sample_name + "_fragLen.txt")
        cmd1 = build_command([tools.perl,
                              tool_path("fragment_length_dist.pl"),
                              rmdup_bam,
                              frag_len])

        fragL_count = os.path.join(QC_folder,
                                   args.sample_name + "_fragCount.txt")
        cmd2 = ("sort -n  " + frag_len + " | uniq -c  > " + fragL_count)

        fragL_dis1 = os.path.join(QC_folder, args.sample_name +
                                  "_fragLenDistribution.pdf")
        fragL_png = os.path.join(QC_folder, args.sample_name +
                                 "_fragLenDistribution.png")
        fragL_dis2 = os.path.join(QC_folder, args.sample_name +
                                  "_fragLenDistribution.txt")

        cmd3 = (tools.Rscript + " " + tool_path("PEPATAC.R") +
                " frag -l " + frag_len + " -c " + fragL_count +
                " -p " + fragL_dis1 + " -t " + fragL_dis2)

        pm.run([cmd1, cmd2, cmd3], fragL_dis1, nofail=True,
               container=pm.container)
        pm.report_object("Fragment distribution", fragL_dis1,
                         anchor_image=fragL_png)
    else: 
        print("Fragment distribution requires paired-end data")

    ############################################################################
    #                        Extract genomic features                          #
    ############################################################################
    # Generate local unzipped annotation file
    anno_local = os.path.join(raw_folder,
                              args.genome_assembly + "_annotations.bed")
    anno_zip = os.path.join(raw_folder,
                            args.genome_assembly + "_annotations.bed.gz")

    if (not os.path.exists(anno_local) and
        not os.path.exists(anno_zip) and
        os.path.exists(res.feat_annotation) or
        args.new_start):

        if res.feat_annotation.endswith(".gz"):
            cmd1 = ("ln -sf " + res.feat_annotation + " " + anno_zip)
            cmd2 = (ngstk.ziptool + " -d -c " + anno_zip +
                    " > " + anno_local)
            pm.run([cmd1, cmd2], anno_local)
            pm.clean_add(anno_local)
        elif res.feat_annotation.endswith(".bed"):
            cmd = ("ln -sf " + res.feat_annotation + " " + anno_local)
            pm.run(cmd, anno_local)
            pm.clean_add(anno_local)
        else:
            print("Skipping read and peak annotation...")
            print("This requires a {} annotation file."
                  .format(args.genome_assembly))
            print("Could not find {}.`"
                  .format(str(os.path.dirname(res.feat_annotation))))

    ############################################################################
    #                               Peak calling                               #
    ############################################################################
    pm.timestamp("### Call peaks")

    def report_peak_count():
        num_peaksfile_lines = int(ngstk.count_lines(peak_output_file).strip())
        num_peaks = max(0, num_peaksfile_lines - 1)
        pm.report_result("Peak_count", num_peaks)

    peak_folder = os.path.join(param.outfolder, "peak_calling_" +
                               args.genome_assembly)
    ngstk.make_dir(peak_folder)
    peak_output_file = os.path.join(peak_folder,  args.sample_name +
                                    "_peaks.narrowPeak")
    fixed_peak_file = os.path.join(peak_folder,  args.sample_name +
                                    "_peaks_fixedWidth.narrowPeak")
    norm_fixed_peak_file = os.path.join(peak_folder,  args.sample_name +
                                        "_peaks_fixedWidth_normalized.narrowPeak")
    peak_input_file = shift_bed
    bigNarrowPeak = os.path.join(peak_folder,
                                 args.sample_name + "_peaks.bigBed")
    peak_bed = os.path.join(peak_folder, args.sample_name + "_peaks.bed")
    chr_order = os.path.join(peak_folder, "chr_order.txt")
    chr_keep = os.path.join(peak_folder, "chr_keep.txt")

    # TODO: add chr_keep file and the same logic as in PEPPRO
    sort_peak_bed = os.path.join(peak_folder, args.sample_name +
                                 "_peaks_sort.bed")
    peak_coverage = os.path.join(peak_folder, args.sample_name +
                                 "_peaks_coverage.bed")

    if not os.path.isfile(peak_input_file):
        print("Cannot call peaks, {} does not exist.".format(peak_input_file))
        print("Check your reads and alignment to primary genome.")
        pm.stop_pipeline()
    elif os.path.isfile(peak_input_file) and os.stat(peak_input_file).st_size == 0:
        print("Cannot call peaks, {} is empty".format(peak_input_file))
        print("Check your reads and alignment to primary genome.")
        pm.stop_pipeline()
    else:
        if args.peak_caller == "fseq":
            if args.peak_type == "fixed":
                err_msg = "Must use MACS2 when calling fixed width peaks."
                pm.fail_pipeline(RuntimeError(err_msg))
            else:
                fseq_cmd_chunks = [
                    tools.fseq,
                    ("-o", peak_folder),
                    param.fseq.params
                ]
                # Create the peak calling command
                fseq_cmd_chunks.append(peak_input_file)
                fseq_cmd = build_command(fseq_cmd_chunks)

                # Create the file merge/delete commands.
                chrom_peak_files = os.path.join(peak_folder, "*.npf")
                merge_chrom_peaks_files = (
                    "cat {peakfiles} > {combined_peak_file}"
                    .format(peakfiles=chrom_peak_files,
                            combined_peak_file=peak_output_file))
                pm.clean_add(chrom_peak_files)

                # Pypiper serially executes the commands.
                cmd = [fseq_cmd, merge_chrom_peaks_files]
        else:
            # MACS2
            # Note: required input file is non-positional ("treatment" file -t)
            macs_cmd_base = [
                "{} callpeak".format(tools.macs2),
                ("-t", peak_input_file),
                ("--outdir", peak_folder),
                ("-n", args.sample_name),
                ("-g", args.genome_size)
            ]
            if args.peak_type == "variable":
                macs_cmd_base.extend(param.macs2.params.split())
            elif args.peak_type == "fixed":
                fixed_width = ('--shift -75 --extsize 150 --nomodel '
                               '--call-summits --nolambda --keep-dup all '
                               '-p 0.01')
                macs_cmd_base.extend(fixed_width.split())
            else:  # default to variable
                macs_cmd_base.extend(param.macs2.params.split())

        # Call peaks and report peak count.
        cmd = build_command(macs_cmd_base)
        pm.run(cmd, peak_output_file, follow=report_peak_count,
               container=pm.container)

        if args.peak_type == "fixed":
            # extend peaks from summit by 'extend'
            # start extend from center of peak
            cmd = ("awk -v OFS='" + "\t" +
                   "' '{$2 = int(($3 - $2)/2 + $2 - " +
                   str(args.extend) + "); " +
                   "$3 = int($2 + " + str(2*args.extend) +
                   "); print}' " + peak_output_file + " > " + fixed_peak_file)
            peak_output_file = fixed_peak_file
            pm.run(cmd, peak_output_file)
            # remove overlapping peaks
            cmd = build_command([tools.Rscript,
                                 (tool_path("PEPATAC.R"), "reduce"),
                                 ("-i", fixed_peak_file),
                                 ("-c", res.chrom_sizes)
                                ])
            pm.run(cmd, norm_fixed_peak_file, nofail=False)
            peak_output_file = norm_fixed_peak_file
            pm.clean_add(fixed_peak_file)

        # Filter peaks in blacklist.
        # TODO: improve documentation of using a blacklist
        if os.path.exists(res.blacklist):
            filter_peak = os.path.join(peak_folder, args.sample_name +
                                       "_peaks_rmBlacklist.narrowPeak")

            if not os.path.exists(filter_peak) or args.new_start:
                black_local = ''
                if res.blacklist.endswith(".gz"):
                    black_zip = os.path.join(raw_folder,
                                             args.genome_assembly +
                                             "_blacklist.bed.gz")
                    black_local = os.path.join(raw_folder,
                                               args.genome_assembly +
                                               "_blacklist.bed")
                    cmd1 = ("ln -sf " + res.blacklist + " " + black_zip)
                    cmd2 = (ngstk.ziptool + " -d -c " + black_zip +
                            " > " + black_local)
                    pm.run([cmd1, cmd2], black_local)
                    pm.clean_add(black_local)
                elif res.blacklist.endswith(".bed"):
                    black_local = os.path.join(raw_folder,
                                               args.genome_assembly +
                                               "_blacklist.bed")
                    cmd = ("ln -sf " + res.feat_annotation + " " + black_local)
                    pm.run(cmd, black_local)
                else:
                    print("Skipping peak filtering...")
                    print("This requires a {} blacklist file."
                          .format(args.genome_assembly))
                    print("Could not find {}.`"
                          .format(str(os.path.dirname(res.blacklist))))

                if os.path.exists(black_local):
                    cmd = (tools.bedtools + " intersect " + " -a " +
                           peak_output_file + " -b " + black_local +
                           " -v  >" + filter_peak)
                    peak_output_file = filter_peak
                    pm.run(cmd, filter_peak)

        ########################################################################
        #                Determine the fraction of reads in peaks              #
        ########################################################################
        pm.timestamp("### Calculate fraction of reads in peaks (FRiP)")

        if pm.get_stat("FRiP") is None or args.new_start:
            frip = calc_frip(rmdup_bam, peak_output_file,
                             frip_func=ngstk.simple_frip,
                             pipeline_manager=pm)
            pm.report_result("FRiP", round(frip, 2))

        if  os.path.exists(res.frip_ref_peaks):
            # Use an external reference set of peaks instead of the peaks
            # called from this run
            frip_ref = calc_frip(rmdup_bam, res.frip_ref_peaks,
                                 frip_func=ngstk.simple_frip,
                                 pipeline_manager=pm)
            pm.report_result("FRiP_ref", round(frip_ref, 2))

        # Produce bigBed (bigNarrowPeak) file from MACS/Fseq narrowPeak file
        pm.timestamp("### # Produce bigBed formatted narrowPeak file")
        cmd = build_command(
                [tools.Rscript, tool_path("PEPATAC.R"), "bigbed", 
                 ("-i", peak_output_file),
                 ("-c", res.chrom_sizes),
                 ("-t", tools.bedToBigBed)
                ])
        pm.run(cmd, bigNarrowPeak, nofail=False)
        
        ########################################################################
        #                        Calculate peak coverage                       #
        ########################################################################
        pm.timestamp("### Calculate peak coverage")

        if not os.path.exists(peak_coverage) or args.new_start:
            cmd1 = ("cut -f 1-3 " + peak_output_file + " > " + peak_bed)
            cmd2 = (tools.samtools + " view -H " + rmdup_bam +
                    " | grep 'SN:' | awk -F':' '{print $2,$3}' | " +
                    "awk -F' ' -v OFS='\t' '{print $1,$3}' > " + chr_order)
            cmd3 = ("cut -f 1 " + chr_order + " > " + chr_keep)
            cmd4 = (tools.bedtools + " sort -i " + peak_bed + " -faidx " +
                    chr_order + " > " + sort_peak_bed)
            pm.run([cmd1, cmd2, cmd3, cmd4], sort_peak_bed, nofail=True,
                   container=pm.container)
        
        cmd4 = (tools.bedtools + " coverage -sorted -counts -a " +
                sort_peak_bed + " -b " + rmdup_bam + " -g " + chr_order +
                " > " + peak_coverage)
        pm.run(cmd4, peak_coverage, nofail=True)
        
        pm.clean_add(peak_bed)
        pm.clean_add(chr_order)
        pm.clean_add(chr_keep)
        pm.clean_add(sort_peak_bed)

        ########################################################################
        #                             Annotate peaks                           #
        ########################################################################
        pm.timestamp("### Annotate peaks")

        chr_PDF  = os.path.join(QC_folder, 
            args.sample_name + "_chromosome_distribution.pdf")
        chr_PNG  = os.path.join(QC_folder,
            args.sample_name + "_chromosome_distribution.png")
        TSSdist_PDF = os.path.join(QC_folder,
            args.sample_name + "_TSS_distribution.pdf")
        TSSdist_PNG = os.path.join(QC_folder,
            args.sample_name + "_TSS_distribution.png")
        gd_PDF  = os.path.join(QC_folder,
            args.sample_name + "_genomic_distribution.pdf")
        gd_PNG  = os.path.join(QC_folder,
            args.sample_name + "_genomic_distribution.png")

        cmd1 = build_command(
                [tools.Rscript,
                 (tool_path("PEPATAC.R"), "anno"),
                 ("-p", "chromosome"),
                 ("-i", peak_output_file),
                 ("-f", anno_local),
                 ("-g", args.genome_assembly),
                 ("-o", chr_PDF)
                ])
        cmd2 = build_command(
                [tools.Rscript,
                 (tool_path("PEPATAC.R"), "anno"),
                 ("-p", "tss"),
                 ("-i", peak_output_file),
                 ("-f", anno_local),
                 ("-g", args.genome_assembly),
                 ("-o", TSSdist_PDF)
                ])
        cmd3 = build_command(
                [tools.Rscript,
                 (tool_path("PEPATAC.R"), "anno"),
                 ("-p", "genomic"),
                 ("-i", peak_output_file),
                 ("-f", anno_local),
                 ("-g", args.genome_assembly),
                 ("-o", gd_PDF)
                ])

        if os.path.isfile(anno_local):
            if not os.path.exists(chr_PDF):
                pm.run(cmd1, chr_PDF)
                pm.report_object("Peak chromosome distribution", chr_PDF,
                                 anchor_image=chr_PNG)
            if not os.path.exists(TSSdist_PDF):
                pm.run(cmd2, TSSdist_PDF)
                pm.report_object("TSS distance distribution", TSSdist_PDF,
                                 anchor_image=TSSdist_PNG)
            if not os.path.exists(gd_PDF):
                pm.run(cmd3, gd_PDF)
                pm.report_object("Peak partition distribution", gd_PDF,
                                 anchor_image=gd_PNG)

        ########################################################################
        #                       Perform motif analysis                         #
        ########################################################################
        if args.motif:
            pm.timestamp("### Motif analysis")

            # convert narrowPeak to BED6
            peak_bed_file = os.path.join(peak_folder,  args.sample_name +
                                         "_peaks.bed")
            if os.path.exists(peak_output_file) and os.stat(peak_output_file).st_size > 0:
                cmd = ("cut -f 1-6 " + peak_output_file + " > " + peak_bed_file)
                pm.run(cmd, peak_bed_file)
                pm.clean_add(peak_bed_file) 
                # create preparsed directory
                tempdir = tempfile.mkdtemp(dir=peak_folder)
                pm.clean_add(tempdir)
                # perform motif analysis
                motif_HTML  = os.path.join(peak_folder, "homerResults.html")
                cmd = ("findMotifsGenome.pl " + peak_bed_file + " " +
                       args.genome_assembly + " " + peak_folder +
                       " -size given -mask -preparsedDir " + tempdir)
                pm.run(cmd, motif_HTML)
                pm.report_object("Motif analysis", motif_HTML)
            elif not os.path.exists(peak_output_file):
                print("Cannot perform motif enrichment.")
                print("Could not find {}".format(peak_output_file))
                pm.stop_pipeline()
            elif os.stat(peak_output_file).st_size == 0:
                print("Cannot perform motif enrichment.")
                print("{} is empty.".format(peak_output_file))
                pm.stop_pipeline()
            else:
                print("Cannot perform motif enrichment.")
                print("Confirm peak calling was successful.")
                pm.stop_pipeline()

    ############################################################################ 
    #                  Determine genomic feature coverage                      #
    ############################################################################
    pm.timestamp("### Calculate read coverage")

    #frif_PDF = os.path.join(QC_folder, args.sample_name + "_frif.pdf")
    #frif_PNG = os.path.join(QC_folder, args.sample_name + "_frif.png")

    # Cummulative Fraction of Reads in Features (cFRiF)
    cFRiF_PDF = os.path.join(QC_folder, args.sample_name + "_cFRiF.pdf")
    cFRiF_PNG = os.path.join(QC_folder, args.sample_name + "_cFRiF.png")

    # Fraction of Reads in Feature (FRiF)
    FRiF_PDF = os.path.join(QC_folder, args.sample_name + "_FRiF.pdf")
    FRiF_PNG = os.path.join(QC_folder, args.sample_name + "_FRiF.png")

    if not os.path.exists(cFRiF_PDF) or args.new_start:
        anno_list = list()
        anno_files = list()

        if os.path.isfile(anno_local):
            # Get list of features
            if args.prioritize:
                cmd1 = ("cut -f 4 " + anno_local + " | uniq")
            else:
                cmd1 = ("cut -f 4 " + anno_local + " | sort -u")
            ft_list = pm.checkprint(cmd1, shell=True)
            ft_list = ft_list.splitlines()

            # Split annotation file on features
            cmd2 = ("awk -F'\t' '{print>\"" + QC_folder + "/\"$4}' " +
                    anno_local)

            if args.prioritize:
                if len(ft_list) >= 1:
                    for pos, anno in enumerate(ft_list):
                        # working files
                        anno_file = os.path.join(QC_folder, str(anno))
                        valid_name = str(re.sub('[^\w_.)( -]', '', anno).strip().replace(' ', '_'))
                        file_name = os.path.join(QC_folder, valid_name)
                        anno_sort = os.path.join(QC_folder,
                                                 valid_name + "_sort.bed")
                        anno_cov = os.path.join(QC_folder,
                                                args.sample_name + "_" +
                                                valid_name + "_coverage.bed")

                        # Extract feature files
                        pm.run(cmd2, anno_file)

                        # Rename files to valid file_names
                        # Avoid 'mv' "are the same file" error
                        if not os.path.exists(file_name):
                            cmd = 'mv "{old}" "{new}"'.format(old=anno_file,
                                                              new=file_name)
                            pm.run(cmd, file_name)

                        # Sort files (ensure only aligned chromosomes are kept)
                        # Need to cut -f 1-6 if you want strand information
                        # Not all features are stranded
                        # TODO: check for strandedness (*only works on some features)
                        if not os.path.exists(chr_order):
                            cmd = (tools.samtools + " view -H " + rmdup_bam +
                                   " | grep 'SN:' | awk -F':' '{print $2,$3}' | " +
                                   "awk -F' ' -v OFS='\t' '{print $1,$3}' > " + chr_order)
                            pm.run(cmd, chr_order)
                            pm.clean_add(chr_order)


                        cmd3 = ("cut -f 1 " + chr_order + " | grep -wf - " +
                                file_name + " | cut -f 1-3 | " +
                                "bedtools sort -i stdin -faidx " +
                                chr_order + " | bedtools merge -i stdin > " +                           
                                anno_sort)
                        # for future stranded possibilities include for merge
                        # "-c 4,5,6 -o collapse,collapse,collapse > " +
                        pm.run(cmd3, anno_sort)
                
                        anno_files.append(anno_sort)
                        anno_list.append(anno_cov)

                        pm.clean_add(file_name)
                        pm.clean_add(anno_sort)
                        pm.clean_add(anno_cov)

                    # Iteratively prioritize annotations by order presented
                    anno_files.reverse()
                    if len(anno_files) >= 1:
                        idx = list(range(0,len(anno_files)))
                        #idx.reverse()
                        file_count = 1
                        for annotation in anno_files:
                            del idx[0]
                            if file_count < len(anno_files):
                                file_count += 1
                                for i in idx:
                                    if annotation is not anno_files[i]:
                                        os.path.join(QC_folder)
                                        temp = tempfile.NamedTemporaryFile(dir=QC_folder, delete=False)
                                        #os.chmod(temp.name, 0o771)
                                        cmd1 = ("bedtools subtract -a " +
                                                annotation + " -b " +
                                                anno_files[i] + " > " + 
                                                temp.name)
                                        cmd2 = ("mv " + temp.name +
                                                " " + annotation)
                                        pm.run([cmd1, cmd2], cFRiF_PDF)
                                        temp.close()

                    anno_list.reverse()
                    if len(anno_files) >= 1:
                        for idx, annotation in enumerate(anno_files):
                            # Identifies unstranded coverage
                            # Would need to use '-s' flag to be stranded
                            if os.path.isfile(annotation) and os.stat(annotation).st_size > 0:
                                cmd3 = (tools.bedtools +
                                        " coverage -sorted -a " +
                                        annotation + " -b " + rmdup_bam +
                                        " -g " + chr_order + " > " +
                                        anno_list[idx])
                                pm.run(cmd3, cFRiF_PDF)
            else:
                if len(ft_list) >= 1:
                    for pos, anno in enumerate(ft_list):
                        # working files
                        anno_file = os.path.join(QC_folder, str(anno))
                        valid_name = str(re.sub('[^\w_.)( -]', '', anno).strip().replace(' ', '_'))
                        file_name = os.path.join(QC_folder, valid_name)
                        anno_sort = os.path.join(QC_folder,
                                                 valid_name + "_sort.bed")
                        anno_cov = os.path.join(QC_folder,
                                                args.sample_name + "_" +
                                                valid_name + "_coverage.bed")

                        # Extract feature files
                        pm.run(cmd2, anno_file)

                        # Rename files to valid file_names
                        # Avoid 'mv' "are the same file" error
                        if not os.path.exists(file_name):
                            cmd = 'mv "{old}" "{new}"'.format(old=anno_file,
                                                              new=file_name)
                            pm.run(cmd, file_name)

                        # Sort files (ensure only aligned chromosomes are kept)
                        # Need to cut -f 1-6 if you want strand information
                        # Not all features are stranded
                        # TODO: check for strandedness
                        if not os.path.exists(chr_order):
                            cmd = (tools.samtools + " view -H " + rmdup_bam +
                                   " | grep 'SN:' | awk -F':' '{print $2,$3}' | " +
                                   "awk -F' ' -v OFS='\t' '{print $1,$3}' > " + chr_order)
                            pm.run(cmd, chr_order)
                            pm.clean_add(chr_order)

                        cmd3 = ("cut -f 1 " + chr_order + " | grep -wf - " +
                                file_name + " | cut -f 1-3 | " +
                                "bedtools sort -i stdin -faidx " +
                                chr_order + " > " + anno_sort)
                        pm.run(cmd3, anno_sort)
                        
                        anno_list.append(anno_cov)
                        # Identifies unstranded coverage
                        # Would need to use '-s' flag to be stranded
                        cmd4 = (tools.bedtools + " coverage -sorted " +
                                " -a " + anno_sort + " -b " + rmdup_bam +
                                " -g " + chr_order + " > " + anno_cov)
                        pm.run(cmd4, anno_cov)

                        pm.clean_add(file_name)
                        pm.clean_add(anno_sort)
                        pm.clean_add(anno_cov)
    

    ############################################################################
    #                             Plot FRiF or FRiP                            #
    ############################################################################
    pm.timestamp("### Calculate cumulative and terminal fraction of reads in features (cFRiF/FRiF)")

    # Calculate size of genome
    if not pm.get_stat("Genome_size") or args.new_start:
        genome_size = int(pm.checkprint(
            ("awk '{sum+=$2} END {printf \"%.0f\", sum}' " +
             res.chrom_sizes)))
        pm.report_result("Genome_size", genome_size)
    else:
        genome_size = int(pm.get_stat("Genome_size"))

    if not os.path.exists(cFRiF_PDF) or args.new_start:
        if args.prioritize:
            # Count bases, not reads
            # return to original priority ranked order
            anno_list.reverse()
            count_cmd = (tools.bedtools + " genomecov -ibam " + rmdup_bam +
                         " -bg | awk '{sum+=($3-$2)}END{print sum}'")
        else:
            # Count reads
            count_cmd = (tools.samtools + " view -@ " + str(pm.cores) + " " +
                         param.samtools.params + " -c -F4 " + rmdup_bam)

        read_count = pm.checkprint(count_cmd)
        read_count = str(read_count).rstrip()

        # cfrif_cmd = [tools.Rscript, tool_path("PEPATAC.R"), "cfrif",
        #              "-n", args.sample_name, "-r", total_reads,
        #              "-o", cFRiF_PDF, "--bed"]
        # frif_cmd = [tools.Rscript, tool_path("PEPATAC.R"), "frif",
        #              "-n", args.sample_name, "-r", total_reads,
        #              "-o", FRiF_PDF, "--bed"]

        cFRiF_cmd = [tools.Rscript, tool_path("PEPATAC.R"), "frif",
                     "-s", args.sample_name, "-z", str(genome_size).rstrip(),
                     "-n", read_count, "-y", "cfrif"]

        FRiF_cmd = [tools.Rscript, tool_path("PEPATAC.R"), "frif",
                    "-s", args.sample_name, "-z", str(genome_size).rstrip(),
                    "-n", read_count, "-y", "frif"]

        if not args.prioritize:
            # Use reads for calculation
            cFRiF_cmd.append("--reads")
            FRiF_cmd.append("--reads")

        cFRiF_cmd.append("-o")
        cFRiF_cmd.append(cFRiF_PDF)
        cFRiF_cmd.append("--bed")

        FRiF_cmd.append("-o")
        FRiF_cmd.append(FRiF_PDF)
        FRiF_cmd.append("--bed")

        if anno_list:
            for cov in anno_list:
                if os.path.isfile(cov) and os.stat(cov).st_size > 0:
                    cFRiF_cmd.append(cov)
                    FRiF_cmd.append(cov)
            cmd = build_command(cFRiF_cmd)
            pm.run(cmd, cFRiF_PDF, nofail=False)
            pm.report_object("cFRiF", cFRiF_PDF, anchor_image=cFRiF_PNG)

            cmd = build_command(FRiF_cmd)
            pm.run(cmd, FRiF_PDF, nofail=False)
            pm.report_object("FRiF", FRiF_PDF, anchor_image=FRiF_PNG)


    ############################################################################
    #            Remove all but final output files to save space               #
    ############################################################################
    if args.lite:
        # Remove everything but ultimate outputs
        pm.clean_add(fragL)
        pm.clean_add(fragL_dis2)
        pm.clean_add(fragL_count)
        pm.clean_add(peak_coverage)
        pm.clean_add(shift_bed)
        pm.clean_add(Tss_enrich)
        pm.clean_add(mapping_genome_bam)
        pm.clean_add(mapping_genome_index)
        pm.clean_add(failQC_genome_bam)
        pm.clean_add(unmap_genome_bam)
        for unmapped_fq in to_compress:
            if not unmapped_fq:
                pm.clean_add(unmapped_fq + ".gz")

    ############################################################################
    #                            PIPELINE COMPLETE!                            #
    ############################################################################
    pm.stop_pipeline()


if __name__ == '__main__':
    pm = None
    # TODO: remove once ngstk become less instance-y, more function-y.
    ngstk = None
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit("Pipeline aborted")
