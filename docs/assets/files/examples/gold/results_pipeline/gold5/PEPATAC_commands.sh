# Pipeline started at 09-17 15:47:24

ln -sf /sfs/lustre/allocations/shefflab/data/sra_fastq/SRR5210390_1.fastq.gz /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/raw/gold5_R1.fastq.gz

ln -sf /sfs/lustre/allocations/shefflab/data/sra_fastq/SRR5210390_2.fastq.gz /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/raw/gold5_R2.fastq.gz

pigz -p 8 -d -c /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/raw/gold5_R1.fastq.gz > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R1.fastq

pigz -p 8 -d -c /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/raw/gold5_R2.fastq.gz > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R2.fastq

skewer -f sanger -t 8 -m pe -x /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/NexteraPE-PE.fa --quiet -o /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R1.fastq /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R2.fastq

mv /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5-trimmed-pair1.fastq /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R1.trim.fastq

mv /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5-trimmed-pair2.fastq /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R2.trim.fastq

fastqc --noextract --outdir /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastqc /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R1.trim.fastq

fastqc --noextract --outdir /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastqc /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R2.trim.fastq

mkfifo /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/bt2

perl /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/filter_paired_fq.pl /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/bt2 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R1.trim.fastq /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R2.trim.fastq /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/gold5_rCRSd_unmap_R1.fq /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/gold5_rCRSd_unmap_R2.fq

(bowtie2 -p 8 -k 1 -D 20 -R 3 -N 1 -L 20 -i S,1,0.50 -x /nm/t1/genomes/rCRSd/indexed_bowtie2/rCRSd --rg-id gold5 -U /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/fastq/gold5_R1.trim.fastq --un /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/bt2 > /dev/null) 2>/sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/gold5_rCRSd_bt_aln_summary.log

grep 'aligned exactly 1 time' /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/gold5_rCRSd_bt_aln_summary.log | awk '{print $1}'

bowtie2 -p 8 --very-sensitive -X 2000 --rg-id gold5 -x /nm/t1/genomes/hg19/indexed_bowtie2/hg19 -1 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/gold5_rCRSd_unmap_R1.fq -2 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/prealignments/gold5_rCRSd_unmap_R2.fq | samtools view -bS - -@ 1  | samtools sort - -@ 1 -T /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/tmpZZADBE -o /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_temp.bam

samtools view -q 10 -b -@ 8 -f 2 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_temp.bam > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort.bam

samtools index /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort.bam

/sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/bamQC.py -i /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort.bam -c 8 -o /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_bamQC.tsv

awk '{ for (i=1; i<=NF; ++i) { if ($i ~ "NRF") c=i } getline; print $c }' /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_bamQC.tsv

awk '{ for (i=1; i<=NF; ++i) { if ($i ~ "PBC1") c=i } getline; print $c }' /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_bamQC.tsv

awk '{ for (i=1; i<=NF; ++i) { if ($i ~ "PBC2") c=i } getline; print $c }' /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_bamQC.tsv

samtools view -b -@ 8 -f 12  /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_temp.bam > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_unmap.bam

java -Xmx15200m -jar /sfs/lustre/scratch/jps3dp/tools/picard/build/libs/picard.jar MarkDuplicates INPUT=/sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort.bam OUTPUT=/sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam METRICS_FILE=/sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_picard_metrics_bam.txt VALIDATION_STRINGENCY=LENIENT ASSUME_SORTED=true REMOVE_DUPLICATES=true > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_picard_metrics_log.txt

samtools index /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam

awk -F'	' -f /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/extract_post_dup_aligned_reads.awk /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_picard_metrics_bam.txt

/sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/bamSitesToWig.py -i /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -c /nm/t1/genomes/hg19/hg19.chromSizes -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19_exact/gold5_shift.bed -o /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19_exact/gold5_exact.bw -w /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_smooth.bw -p 5

touch /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19_exact/temp/flag_completed

/sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/pyTssEnrichment.py -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -b /nm/t1/genomes/hg19/hg19_TSS.tsv -p ends -c 8 -e 2000 -u -v -s 4 -o /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_TssEnrichment.txt

Rscript /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/PEPATAC_TSSenrichmentPlot.R /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_TssEnrichment.txt pdf

perl /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/fragment_length_dist.pl /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragLen.txt

sort -n  /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragLen.txt | uniq -c  > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragCount.txt

Rscript /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/fragment_length_dist.R /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragLen.txt /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragCount.txt /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragLenDistribution.pdf /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_fragLenDistribution.txt

macs2 callpeak -t /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19_exact/gold5_shift.bed -f BED -g hs --outdir /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19 -n gold5 -q 0.01 --shift 0 --nomodel

samtools view -@ 4 -c -L /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.narrowPeak /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam

Rscript /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/narrowPeakToBigBed.R /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.narrowPeak /nm/t1/genomes/hg19/hg19.chromSizes bedToBigBed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.bigBed

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.narrowPeak > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.bed

samtools view -H /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam | grep 'SN:' | awk -F':' '{print $2,$3}' | awk -F' ' -v OFS='	' '{print $1,$3}' > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt

bedtools sort -i /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.bed -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks_coverage.bed

zcat /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/anno/hg19_annotations.bed.gz | cut -f 4 | sort -u

zcat /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/anno/hg19_annotations.bed.gz | awk -F'	' '{print>"/sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/"$4}'

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/3_UTR | bedtools sort -i stdin -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/3_UTR_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/3_UTR_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_3_UTR_coverage.bed

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/5_UTR | bedtools sort -i stdin -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/5_UTR_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/5_UTR_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_5_UTR_coverage.bed

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Exon | bedtools sort -i stdin -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Exon_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Exon_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Exon_coverage.bed

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Intron | bedtools sort -i stdin -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Intron_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Intron_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Intron_coverage.bed

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Promoter | bedtools sort -i stdin -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Promoter_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Promoter_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Promoter_coverage.bed

cut -f 1-3 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Promoter_Flanking_Region | bedtools sort -i stdin -faidx /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Promoter_Flanking_Region_sort.bed

bedtools coverage -sorted -counts -a /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/Promoter_Flanking_Region_sort.bed -b /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam -g /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/chr_order.txt > /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Promoter_Flanking_Region_coverage.bed

samtools view -@ 8 -q 15 -c -F4 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/aligned_hg19/gold5_sort_dedup.bam

Rscript /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/PEPATAC_frip.R /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks_coverage.bed 71491888 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_frif.pdf --bed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_3_UTR_coverage.bed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_5_UTR_coverage.bed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Exon_coverage.bed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Intron_coverage.bed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Promoter_coverage.bed /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19/gold5_Promoter_Flanking_Region_coverage.bed

Rscript /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/tools/PEPATAC_annotation.R /sfs/lustre/scratch/jps3dp/DATA/pepatac/tutorial/tools/pepatac/anno/hg19_annotations.bed.gz /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/peak_calling_hg19/gold5_peaks.narrowPeak gold5 hg19 /sfs/lustre/allocations/shefflab/processed/gold/pepatac/hg19/09_17_18/results_pipeline/gold5/QC_hg19
