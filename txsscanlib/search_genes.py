# -*- coding: utf-8 -*-

###############################
# Created on Jan 9, 2013
#
# @author: bneron
# @contact: bneron@pasteur.fr
# @organization: Institut Pasteur
# @license: GPLv3
################################

import threading
import logging
_log = logging.getLogger('txsscan.' + __name__)

import shutil
import os.path
from report import GembaseHMMReport, GeneralHMMReport

def search_genes(genes, cfg):
    """
    For each gene of the list, use the corresponding profile to perform an HMMer search, and parse the output
    to generate a HMMReport that is saved in a file after Hit filtering. These tasks are performed in parrallel using threads.
    The number of workers can be limited by worker_nb directive in the config object or in the command-line with the \"-w\" option.
    
    :param genes: the genes to search in the input sequence dataset
    :type genes: list of :class:`txsscanlib.gene.Gene` objects
    :param cfg: the configuration object
    :type cfg: :class:`txsscanlib.config.Config` object
    """
    worker_nb = cfg.worker_nb
    if not worker_nb:
        worker_nb = len(genes)
    _log.debug("worker_nb = %d" % worker_nb)
    sema = threading.BoundedSemaphore(value = worker_nb)
    all_reports = []
    
    def search(gene, all_reports, sema):
        """
        search gene in base (execute \"hmmsearch\") and produce a report
        
        :param gene: the gene to search
        :type gene: a :class:`txsscanlib.gene.Gene` object
        :param all_reports: a container to append the generated Report object
        :type all_reports: list
        :param sema: semaphore to limit the number of parallel workers
        :type sema: a threading.BoundedSemaphore
        """
        with sema:
            _log.info("search gene %s" % gene.name)
            profile = gene.profile
            report = profile.execute()
            report.extract()
            report.save_extract()
            all_reports.append(report)
            
    def recover(gene, all_reports, cfg, sema):
        """
        recover hmmoutput from a previous run and produce a report
        
        :param gene: the gene to search
        :type gene: a :class:`txsscanlib.gene.Gene` object
        :param all_reports: a container to append the generated Report object
        :type all_reports: list
        :param cfg: the configuration 
        :type cfg: :class:`txsscanlib.config.Config` object
        :param sema: semaphore to limit the number of parallel workers
        :type sema: a threading.BoundedSemaphore.
        :return: the list of all HMMReports. 
        :rtype: list of `txsscanlib.report.HMMReport` object.
        """
        with sema:
            hmm_old_path = os.path.join(cfg.previous_run, gene.name + cfg.res_search_suffix)
            _log.info("recover hmm %s" % hmm_old_path)
            hmm_new_path = os.path.join(cfg.working_dir, gene.name + cfg.res_search_suffix)
            shutil.copy(hmm_old_path, hmm_new_path)
            gene.profile.hmm_raw_output = hmm_new_path
            if cfg.db_type == 'gembase':
                report = GembaseHMMReport(gene, hmm_new_path, cfg )
            elif cfg.db_type == 'ordered_replicon':
                report = OrderedHMMReport(gene, hmm_new_path, cfg )
            else:
                report = GeneralHMMReport(gene, hmm_new_path, cfg )
            
            report.extract()
            report.save_extract()
            all_reports.append(report)
            
    #there is only one instance of gene per name but the same instance can be
    #in all genes several times        
    #hmmsearch and extract should be execute only once per run
    #so I uniquify the list of gene
    genes = set(genes)
    _log.debug("start searching genes")
    previous_run = cfg.previous_run
    for gene in genes:
        if previous_run and os.path.exists(os.path.join(previous_run, gene.name + cfg.res_search_suffix)):
            t = threading.Thread(target = recover, args = (gene, all_reports, cfg, sema))
        else:
            t = threading.Thread(target = search, args = (gene, all_reports, sema))
        t.start()
        
    main_thread = threading.currentThread()    
    for t in threading.enumerate():
        if t is main_thread:
            continue
        t.join()
    _log.debug("end searching genes")
    return all_reports
