# Review Change Log & Team Sign-off

This document summarizes the revisions incorporated into the resubmitted **Milestone_1_Reviewed.docx** following the project review meeting.

---

## 1. Change Log

Each row records a revision discussed during the review meeting, the corresponding change made, and the section where it was incorporated.

| # | Revision discussed in review | Change made (confirmed incorporated) | Section / Page |
|---|---|---|---|
| 1 | Remove "agents" / "multi-agent" | Confirmed removed throughout the document | Whole document |
| 2 | Job discovery: API/rate-limit/legal | Added a data-sourcing strategy paragraph (dataset-first approach, no ToS-violating scraping) | Section 7 – Job Discovery |
| 3 | Define ATS score + computation | ATS module dropped from project scope; section removed entirely | Removed |
| 4 | Tailoring hallucination prevention | Added a `facts(R') ⊆ facts(P)` verification-gate paragraph with a faithfulness metric; marked as an optional/stretch goal | Section 7 – Tailoring |
| 5 | Career recommendation methodology | Specified ESCO taxonomy, embedding retrieval, and LLM-generated explanations | Section 7 – Career Recommendation |
| 6 | Job matching methodology | Specified Gemini embeddings, cosine similarity, and weighted rule-based re-ranking | Section 7 – Job Matching |
| 7 | Commit to a specific model | Selected **text-embedding-004** and **Gemini 2.5 Flash** with justification | Section 7 – Architecture |
| 8 | Computational requirements | Added compute and deployment details (cloud free tier, no GPU required) | Section 7 – Architecture |
| 9 | Datasets too generic | Added exact datasets and URLs (Candidate Job Role, CareerBuilder, ESCO) | Section 8 |
| 10 | Ground truth undefined | Defined ground truth for each module, including CareerBuilder application labels | Sections 7 & 9 |
| 11 | Metrics not mapped to implementation | Added a metric-to-ground-truth mapping table for each module | Section 9 |
| 12 | No baselines / qualitative success criteria | Added Random and Cosine Similarity baselines; defined success as outperforming these baselines | Section 7 – Evaluation |
| 13 | Human evaluation methodology undefined | Added Likert-scale rubric and inter-rater agreement protocol | Section 9 |
| 14 | No database / retrieval / vector store | Confirmed PostgreSQL with pgvector/ChromaDB integration | Section 7 |
| 15 | No security / authentication | Confirmed Google SSO and secure cookie authentication | Section 7 |
| 16 | No privacy architecture | Confirmed Presidio-based PII redaction | Section 7 |
| 17 | Prompting / caching / latency | Added a consolidated subsection covering prompting, caching, and latency optimization | Section 7 |
| 18 | Limitations (scraping/API dependency) | Added explicit limitations regarding scraping and API quota dependencies | Section 10 |
| 19 | One end-to-end example | Expanded into a complete walkthrough with concrete example outputs | Section 7 – Overview |

---

------------------------------------------------------------------------

# Milestone 2 Review --- Change Log and Required Revisions

## 1. Purpose

This change log records the revisions made in response to the Milestone
2 review feedback and the requested clarification of the end-to-end
system architecture.

The revisions are based on the submitted **Milestone 2 Report** and are
intended to remove ambiguity around dataset suitability, preprocessing
reproducibility, dataset integration, evaluation readiness, and the
unified data flow across Resume Parsing, Career Recommendation, Job
Discovery, and Job Matching.

The Milestone 2 report already establishes three main modules: Resume
Parsing, Career Recommendation, and Job Discovery/Job Matching. It also
states that the system first extracts a structured candidate profile,
then recommends suitable career roles, and finally ranks relevant jobs
based on profile fit.

------------------------------------------------------------------------

## 2. Change Log

  ---------------------------------------------------------------------------------------------
  \#                Review feedback /       Change made / clarification added Location /
                    revision required                                         evidence
  ----------------- ----------------------- --------------------------------- -----------------
  1                 End-to-end system       Added a unified architecture      New Section:
                    architecture and        showing raw datasets →            **End-to-End
                    integrated RAG/data     preprocessing → canonical data    System
                    flow were unclear       layer → candidate profile →       Architecture**
                                            career retrieval → job discovery  
                                            → job matching/ranking → final    
                                            recommendations. Added explicit   
                                            data-flow relationships and       
                                            retrieval stages.                 

  2                 Unified / merged        Clarified that the project does   Dataset
                    dataset was unclear     **not** perform one physical      Integration;
                                            merge of all source datasets.     Architecture
                                            Instead, the modules integrate    
                                            through shared schemas and        
                                            identifiers: Candidate Profile    
                                            for resume output, ESCO           
                                            occupation/skill URIs for career  
                                            data, and candidate-job pair      
                                            construction for matching.        

  3                 Some datasets were      Added suitability justification   Dataset
                    described but not       and limitations for Resume Data,  Identification /
                    justified               ESCO, Candidate Job Role, and     Suitability
                                            LinkedIn Job Postings. LinkedIn   
                                            is explicitly described as        
                                            U.S.-dominated and unsuitable for 
                                            claims about the Indian labour    
                                            market.                           

  4                 Geographic, recency,    Added evidence that only 742 of   Dataset
                    industry, and ESCO      123,849 LinkedIn postings         Suitability
                    coverage of LinkedIn    explicitly mention India          
                    dataset unclear         (\~0.60%), postings cover 24 Mar  
                                            2024--20 Apr 2024, and the        
                                            dataset is multi-industry but     
                                            U.S.-oriented. ESCO alignment     
                                            results are described as coverage 
                                            rather than guaranteed accuracy.  

  5                 Resume dataset          Added deployment consequences and Resume Dataset
                    limitations were        routing for selectable-text PDFs, Limitations /
                    insufficiently          DOCX, image-only PDFs/scans, and  Deployment
                    connected to deployment multi-page resumes. The report    
                                            now distinguishes controlled      
                                            evaluation data from expected     
                                            production inputs.                

  6                 Gold annotation         Clarified that the gold set       Gold Annotation
                    methodology was unclear contains 86 resumes because 43    Methodology
                                            canonical categories × 2          
                                            resumes/category = 86. Selection  
                                            used duplicate isolation and      
                                            fixed random seed 42.             

  7                 Annotation credibility  Explicitly documented that        Gold Annotation
                    / human verification    AI-generated annotations were     QA
                    needed clarification    quality-checked on 15 resumes by  
                                            three team members, while 71 were 
                                            not individually human-verified.  
                                            The set is therefore described as 
                                            a **provisional gold set**, and   
                                            no formal inter-annotator         
                                            agreement was claimed.            

  8                 Annotation quality      Added annotation guidelines,      Annotation
                    assurance was           JSON-schema validation,           Quality Assurance
                    insufficiently          manifest-based consistency        
                    described               checks, category coverage checks, 
                                            field-count checks, empty-field   
                                            checks, and human review against  
                                            original images.                  

  9                 EDA was descriptive     Added explicit EDA →              EDA Findings and
                    rather than             preprocessing/model decisions.    Decisions
                    decision-oriented       Examples include balanced gold    
                                            sampling for the 12.3:1 resume    
                                            category imbalance, lower         
                                            specificity weighting for common  
                                            ESCO skills, higher               
                                            weighting/priority for rare       
                                            skills, and combined              
                                            semantic/title/experience signals 
                                            for job matching.                 

  10                Feature relationships   Added relationships for skill     Feature
                    were missing            frequency by role, education      Relationship
                                            versus role, experience versus    Analysis
                                            salary, employment type versus    
                                            experience, and shared skills     
                                            across occupations.               

  11                Dataset integration     Documented merge keys, schema     Dataset
                    lacked technical detail mappings, conflict resolution,    Integration
                                            missing-relationship handling,    
                                            and validation checks. ESCO files 
                                            are joined through occupationUri  
                                            and skillUri; candidate-job data  
                                            uses a query-document ranking     
                                            structure rather than a direct    
                                            join.                             

  12                Preprocessing was not   Added implementation details      Data
                    sufficiently            including PyMuPDF, MD5, pHash     Preprocessing
                    reproducible            with Hamming-distance threshold   
                                            6, Tesseract OCR sampling,        
                                            pandas/kagglehub, RapidFuzz,      
                                            rank_bm25, BAAI/bge-base-en-v1.5, 
                                            shared experience mapping, and    
                                            validation steps.                 

  13                Data quality metrics    Added raw-versus-prepared counts  Effect of
                    were incomplete         and measurable preprocessing      Preprocessing /
                                            effects, including 8,905 resumes  Data Summary
                                            retained, 97→43 categories, 6,611 
                                            perceptual groups, 3,291          
                                            near-duplicate-group files, 86    
                                            gold records, 3,043→3,039 ESCO    
                                            occupations, and 13,960→13,939    
                                            skills.                           

  14                Train/validation/test   Clarified that Resume Parsing is  Dataset Splitting
                    split needed            zero-shot and therefore has no    
                    justification           training split; its 86-record     
                                            gold set uses 34 development and  
                                            52 test records. Job Matching     
                                            uses 60/20/20 because the         
                                            development sample contains only  
                                            200 candidates, making an         
                                            80/10/10 split less stable.       

  15                Leakage prevention      Added duplicate-group isolation,  Dataset Splitting
                    needed clarification    candidate-level splitting before  / Augmentation
                                            candidate-job pair construction,  
                                            same-split augmentation, and      
                                            prevention of test resumes being  
                                            used as prompt examples.          

  16                Dataset readiness was   Added concrete prepared-data      Dataset
                    assumed rather than     summaries and validation examples Integration /
                    demonstrated            through the Candidate Profile     Prepared Dataset
                                            schema, ESCO role-level records,  
                                            job_text construction, ranking    
                                            signals, and integration          
                                            validation checks.                

  17                Preprocessing           Added explicit benefits and       Preprocessing
                    trade-offs were not     information-loss consequences for Trade-offs
                    sufficiently discussed  experience mapping, title         
                                            normalization, URL/contact        
                                            removal, description truncation,  
                                            qualification grouping, Unknown   
                                            experience handling, and optional 
                                            salary use.                       

  18                Data governance did not Clarified completed controls such Data Governance /
                    clearly distinguish     as exclusion of email/phone from  Privacy
                    completed versus        the parsing schema, redacted      
                    planned actions         public examples, field-level      
                                            encryption for retained           
                                            structured fields, and deletion   
                                            of temporary rendered images.     
                                            Planned/conditional controls such 
                                            as local PII detection for        
                                            selectable-text PDF/DOCX are      
                                            labelled accordingly.             

  19                Preprocessing notebooks Added direct notebook references  Data
                    were not clearly        in the relevant preprocessing     Preprocessing /
                    referenced              sections:                         Dataset Splitting
                                            `resume_dataset_pipeline.ipynb`   
                                            is identified as the complete     
                                            Resume Parsing preprocessing      
                                            implementation; the Job Matching  
                                            preprocessing notebook is         
                                            referenced for sampling and       
                                            pair-count records.               

  20                One preprocessing       Added a                           New Section:
                    pipeline diagram was    preprocessing/data-integration    **Preprocessing
                    requested               flow covering ingestion,          Pipeline**
                                            validation, normalization,        
                                            deduplication, feature            
                                            engineering, schema validation,   
                                            and final prepared datasets.      

  21                Architecture should     Added a common Candidate Profile  New Section:
                    show how modules        as the central hand-off from      **End-to-End
                    integrate into one      Resume Parsing to Career          System
                    system                  Recommendation and Job Matching.  Architecture**
                                            ESCO provides the occupational    
                                            knowledge base, while             
                                            live/offline job postings provide 
                                            job documents for retrieval and   
                                            ranking.                          

  22                RAG pipeline/data flow  Added a RAG-style retrieval flow: New Section:
                    was not visible         candidate profile/query →         **Integrated RAG
                                            embedding/retrieval → ESCO        Pipeline**
                                            occupation context and            
                                            job-document retrieval →          
                                            ranking/re-ranking → grounded     
                                            recommendation/explanation. The   
                                            diagram distinguishes retrieval   
                                            knowledge sources from the        
                                            candidate profile and job corpus. 

  23                Existing Milestone 1    The architecture revision         New Architecture
                    architecture did not    explicitly connects the modules   Figure
                    sufficiently explain    and their inputs/outputs rather   
                    integration             than presenting them as isolated  
                                            components.                       
  ---------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# Milestone 3 Review --- Change Log and Architecture Revisions

## Purpose

This change log documents the revisions made to the Milestone 3 report
in response to the review feedback received after submission.

The changes are based on the submitted **Milestone 3 Review Report**,
the revised Job Matching architecture documents, and the existing
project architecture. The main objective is to clearly separate
**AI/model architecture** from **overall software/system architecture**,
strengthen the Job Matching design, justify architectural decisions, and
provide measurable operational, retrieval, security, scalability, and
cost targets.

------------------------------------------------------------------------

## Change Log

  -----------------------------------------------------------------------------------
  \#                Review feedback       Change incorporated       Evidence /
                                                                    affected section
  ----------------- --------------------- ------------------------- -----------------
  1                 AI model architecture Separated the report into Architecture
                    and overall software  two architectural views:  Overview
                    architecture were     **Model Architecture**    
                    mixed                 and **System/Software     
                                          Architecture**. Storage,  
                                          APIs, databases, retries, 
                                          caching, authentication,  
                                          and deployment are now    
                                          treated as system         
                                          architecture rather than  
                                          model architecture.       

  2                 Module 3 --- Job      Reworked Job Matching as  Job Matching
                    Matching architecture a clear pipeline:         Architecture
                    needed improvement    Candidate Profile →       
                                          embedding → Top-K vector  
                                          retrieval → hard filters  
                                          → hybrid rule scoring →   
                                          reranking → optional      
                                          web-discovery fallback →  
                                          RAG evidence retrieval →  
                                          LLM judge → final         
                                          shortlist.                

  3                 Overall architecture  Added explicit comparison Architectural
                    was not justified     against multi-agent       Decision
                    against alternatives  systems, end-to-end       Rationale
                                          neural ranking, and       
                                          fine-tuned models. The    
                                          modular pipeline was      
                                          selected because the task 
                                          is structured,            
                                          deterministic stages are  
                                          cheaper and easier to     
                                          debug, and labelled       
                                          hiring-outcome data is    
                                          currently insufficient.   

  4                 RAG selection needed  Added rationale for RAG   RAG Architecture
                    justification         over fine-tuning: lower   
                                          data requirements, easier 
                                          knowledge updates,        
                                          evidence-grounded         
                                          responses, lower          
                                          maintenance burden, and   
                                          no need to retrain when   
                                          ESCO/job information      
                                          changes.                  

  5                 Rule scoring + LLM    Clarified that            Hybrid Ranking
                    reasoning needed      deterministic rules       Architecture
                    justification         enforce objective         
                                          constraints consistently  
                                          while the LLM captures    
                                          semantic relationships,   
                                          transferable skills, and  
                                          contextual fit.           

  6                 Rule weights lacked   Documented Skills = 60%,  Rule-Based
                    rationale             Experience = 25%,         Scoring
                                          Location = 15%. These are 
                                          explicitly identified as  
                                          **heuristic baseline      
                                          weights**, not            
                                          empirically learned       
                                          weights.                  

  7                 Final 60% Rule + 40%  Added rationale that the  Final Score
                    LLM weighting lacked  Rule Engine receives      Combination
                    justification         greater weight because it 
                                          is deterministic,         
                                          transparent, and          
                                          consistent, while the LLM 
                                          provides complementary    
                                          semantic judgement.       

  8                 Quantitative targets  Added module-level        Evaluation &
                    were missing for      targets covering          Design Targets
                    modules               Recall@K, Precision@K,    
                                          latency, API response     
                                          time, retrieval latency,  
                                          and web-search/crawling   
                                          time.                     

  9                 RAG architecture      Added Top-K values,       Retrieval &
                    lacked retrieval      chunking strategy,        Knowledge
                    parameters            metadata use, reranking   Components
                                          criteria, evidence        
                                          selection, and            
                                          vector-index update       
                                          strategy.                 

  10                LangChain/LangGraph   Added explanation that    Framework
                    justification was     LangChain provides        Selection
                    weak                  standardized              
                                          LLM/embedding integration 
                                          and structured execution  
                                          components, while         
                                          LangGraph provides state  
                                          management, conditional   
                                          branches, failure         
                                          handling, and explicit    
                                          pipeline observability.   

  11                Google model          Added API cost,           External
                    dependency was        rate-limit, model         Dependency /
                    insufficiently        deprecation, vendor       Vendor Risk
                    discussed             lock-in, embedding        
                                          compatibility, and        
                                          contingency               
                                          considerations.           

  12                Model names were      Standardized model naming Model
                    inconsistent          throughout the            Architecture
                                          architecture: **Gemma 4   
                                          31B**, **Gemini 2.5       
                                          Flash-Lite**, **Gemini    
                                          2.5 Flash**, and          
                                          **gemini-embedding-2**.   
                                          Where exact deployed      
                                          versions remain           
                                          configurable, the report  
                                          states that model         
                                          identifiers must be       
                                          pinned/configurable.      

  13                Computational         Added CPU, RAM, GPU,      Computational
                    requirements were     memory, inference         Requirements
                    missing               latency, API calls per    
                                          request, crawling         
                                          overhead, and estimated   
                                          per-request API cost.     

  14                Security architecture Expanded security         Security
                    was incomplete        architecture to include   Architecture
                                          authentication,           
                                          authorization, API-key    
                                          management, audit         
                                          logging, field-level      
                                          protection for sensitive  
                                          resume data,              
                                          temporary-image deletion, 
                                          and owner-only            
                                          decryption.               

  15                Explainability was    Added explicit            Explainability
                    insufficient          user-facing evidence:     
                                          overall score, matched    
                                          skills, missing skills,   
                                          experience fit, location  
                                          compatibility, semantic   
                                          relevance, retrieved      
                                          evidence, and             
                                          LLM-generated rationale.  

  16                Scalability was       Added stateless           Scalability
                    insufficient          horizontal scaling,       
                                          asynchronous/queued       
                                          retries, caching,         
                                          concurrent API-call       
                                          limits, persistent vector 
                                          indexes, global job       
                                          deduplication, and        
                                          vector/database growth    
                                          considerations.           

  17                Job Matching RAG      Clarified the distinction Job Matching /
                    relationship was      between **generative RAG  RAG
                    ambiguous             in Career                 
                                          Recommendation** and      
                                          **retrieval/evidence      
                                          augmentation in Job       
                                          Matching**. Job Matching  
                                          uses retrieved job        
                                          evidence for the final    
                                          LLM judge rather than     
                                          allowing the LLM to       
                                          independently invent      
                                          scores.                   

  18                Job Matching data     Standardized the          Job Matching
                    flow needed clearer   retrieval flow: Top-K     Pipeline
                    Top-K stages          configurable retrieval    
                                          depth (production         
                                          design), Top-25 candidate 
                                          pool in evaluation, hard  
                                          filtering, Top-15 hybrid  
                                          ranking, Top-5 final      
                                          candidates, and Top-2     
                                          evidence chunks per       
                                          finalist.                 

  19                Failure/retry         Added explicit failure    Reliability
                    behavior needed       boundaries in LangGraph.  Architecture
                    architectural clarity Failed nodes set pipeline 
                                          error state and           
                                          downstream stages stop;   
                                          rate-limit failures are   
                                          queued/retried rather     
                                          than causing uncontrolled 
                                          retry loops.              

  20                Production vs offline Documented                Embedding
                    embedding model       BAAI/bge-base-en-v1.5 as  Architecture
                    distinction needed    the offline evaluation    
                    clarification         model and Gemini          
                                          Embedding API as the      
                                          production option, with a 
                                          requirement to revalidate 
                                          retrieval metrics using   
                                          the production embedding  
                                          model before final        
                                          sign-off.                 

  21                Architecture needed   Clarified interfaces:     Module Interfaces
                    clearer boundaries    Resume Parsing outputs    
                    between modules       Candidate Profile; Career 
                                          Recommendation consumes   
                                          the profile and returns   
                                          ESCO-grounded career      
                                          recommendations; Job      
                                          Discovery supplies jobs;  
                                          Job Matching ranks        
                                          candidate-job pairs and   
                                          returns the final         
                                          shortlist.                

  22                Cost optimization was Added the                 Cost &
                    not sufficiently      token-minimization        Performance
                    emphasized            principle: deterministic  
                                          processing wherever       
                                          possible, batched LLM     
                                          judgement, persistent job 
                                          storage, and reuse of     
                                          crawled/embedded jobs     
                                          across candidates.        

  23                Security and          Added security controls   Security
                    sensitive data        to the system             Architecture
                    handling needed       architecture rather than  
                    integration into      treating privacy as a     
                    architecture          separate textual note.    

  24                Scalability of vector Added persistent vector   Vector Database
                    storage needed        indexing, metadata        Strategy
                    discussion            filtering, index reuse,   
                                          growth monitoring, and    
                                          re-embedding strategy for 
                                          taxonomy/model updates.   
  -----------------------------------------------------------------------------------

------------------------------------------------------------------------
# Milestone 4 Review --- Change Log and Required Revisions

## Purpose

This change log documents the revisions incorporated into the Milestone
4 report in response to the reviewer observations.

The revisions use the final Milestone 4 implementation evidence rather
than repeating the earlier Milestone 3 architecture. In particular, the
final implementation uses **Gemma 4 31B as the Job Discovery/Matching
judge**, **BAAI/bge-base-en-v1.5 for Job Matching embeddings**,
PostgreSQL/pgvector for the live job store, and the actual evaluated
configuration and prompt sweeps reported in Milestone 4.

The main objective is to show that Milestone 4's
implementation/optimization objectives were addressed even though the
project does not perform gradient-based model training.

------------------------------------------------------------------------

## Change Log

  ---------------------------------------------------------------------------------------
  \#                Reviewer          Revision incorporated             Evidence /
                    observation                                         affected section
  ----------------- ----------------- --------------------------------- -----------------
  1                 Traditional       Added an explicit **Traditional   New section:
                    training          ML → LLM-equivalent activity      **Milestone 4
                    activities were   mapping**: Training → prompt      Activity
                    repeatedly        engineering; hyperparameter       Mapping**
                    described as not  tuning →                          
                    applicable        prompt/schema/retrieval/scoring   
                                      tuning; optimizer → configuration 
                                      optimization; regularization →    
                                      guardrails, schema validation and 
                                      deterministic constraints.        

  2                 Little concrete   Expanded implementation evidence  Implementation
                    evidence that     with sample resume JSON, ESCO     Evidence
                    modules work      retrieval/output, Job Matching    
                                      results, discovery JSON, prompt   
                                      sweep results, and quantitative   
                                      implementation statistics.        

  3                 Prompt iterations Added the number of prompt        Prompt
                    were not          variants tested, what changed     Engineering
                    explained         between variants, selection       
                                      criteria, and examples of         
                                      corrected behaviour. Query        
                                      generation tested 7 variants;     
                                      judge tested 6 variants.          

  4                 Many              Explicitly labelled heuristic     Configuration
                    configuration     parameters and distinguished them Selection
                    values were       from values supported by the      
                    heuristic         Milestone 4 sweeps.               

  5                 Little evidence   Added configuration comparison    Optimization
                    of                tables for Job Matching,          Experiments
                    tuning/ablation   Search/Crawl, Query Generation,   
                                      and Judge prompts.                

  6                 Frozen            Added acceptance criteria: schema Final
                    configuration was validity, ranking quality,        Configuration
                    not justified     latency, reliability, and         Selection
                                      operational constraints. Rejected 
                                      configurations are documented.    

  7                 Implementation    Added resumes processed, ESCO     Quantitative
                    maturity metrics  indexing statistics, ranking      Implementation
                    missing           latency, discovery latency, crawl Statistics
                                      success, query-generation         
                                      latency, judge latency, and live  
                                      LLM call counts.                  

  8                 "No visible       Replaced this with a measurable   Resume Prompt
                    improvement" was  stopping principle: schema        Selection
                    subjective        stability, no new development-set 
                                      errors, stable field extraction,  
                                      and measurable                    
                                      prompt/configuration comparison.  

  9                 Architecture      Replaced the previous             Final
                    differed from     architecture with the **final     Implementation
                    Milestone 3       implementation architecture**,    Architecture
                                      including Gemma 4 31B as the Job  
                                      Matching judge and the actual     
                                      PostgreSQL/pgvector data flow.    

  10                Data-flow         Clarified the stores and paths:   Final Data Flow
                    representations   Candidate Profile is stored in    
                    were incorrect    PostgreSQL; ESCO is retrieved     
                                      through the Career Recommendation 
                                      vector store; live Job Matching   
                                      data and embeddings are stored in 
                                      PostgreSQL/pgvector;              
                                      SearXNG/Crawl4AI feed new jobs    
                                      back into the live job store.     

  11                Metrics           Added a consolidated table of     Evaluation Plan
                    repeatedly        metrics planned for Milestone 5   
                    deferred to       for Resume Parsing, Career        
                    Milestone 5       Recommendation, Job Discovery,    
                                      and Job Matching.                 

  12                Milestone 4       Added measured results while      Results vs
                    implementation    clearly distinguishing **observed Targets
                    maturity needed   implementation results** from     
                    clearer evidence  **future evaluation targets**.    
  ---------------------------------------------------------------------------------------

------------------------------------------------------------------------


## 2. Team Sign-off

Each team member confirms that they have reviewed and approved the final submission.

| Team Member | Reviewed & Approved | Initials | Date |
|---|---|---|---|
| Gaurav Kumar | Y | GK | 2026-07-07 |
| Dev Gupta | Y | DG | 2026-07-07 |
| Pranav N | Y | PrN | 2026-07-07 |
| Praveena N | Y | PvN | 2026-07-07 |
| Abhinav Ohri | Y | AO | 2026-07-07 |

