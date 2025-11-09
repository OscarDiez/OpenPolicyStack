from data_evaluation import TotalFundingByFPOverTime, TotalFundingbyFP,TotalFundingByLLMCategoryOverTime, OrganizationsByCountryGroupOverTime, OrganizationTypeByCountryGroupOverTime        
import os

class sourcing_settings: 
    suppress_ft_crawl = False
    raw_projects_filename = "data/raw_project_ft_data.pickle"
    raw_organizations_filename = "data/raw_orga_ft_data.pickle"


class quantum_settings:
    topic = "quantum"

    if not os.path.exists(f"data/{topic}"):
        os.makedirs(f"data/{topic}")

    if not os.path.exists(f"deliverables/{topic}"):
        os.makedirs(f"deliverables/{topic}")

    data_source = "f&t"

    manual_project_data_filename = f'data/{topic}/input_manual_projects.csv'
    manual_orga_data_filename = f'data/{topic}/input_manual_orgas.csv'
    
    filtered_projects_filename= f'data/{topic}/filtered_projects.csv'
    filtered_organizations_filename = f'data/{topic}/filtered_organizations.csv'
    filtered_prev_projects_filename = f'data/{topic}/filtered_projects_prev.csv'
    processed_diff_projects_filename = f'data/{topic}/processed_projects_diff.csv'

    matchscore_histogram_filename = f'data/{topic}/matchscore_histogram.png'

    db_filename = f'deliverables/{topic}/{topic}.db'

    
    llm_location = "remote"


    suppress_llm_categorization = False
    import_manual_data = True
    send_deliverable = False
    send_newsletter = True


    match_score_threshold = 1



    keyword_list = ["quantum", "quantum mechanic", " qt ", "quantum flagship", "qt flagship", "qubit", "trapped ion", "quantum cryptography", "quantum communic", "quantum dyn", "quantum comput",
            "quantum simula", "quantum dot", "supercoducting qubit", "neutral atoms", "quantum physic", "quantum optic", "quantum circuit", "quantum superposit", "quantum metrology", "quantum sens",
            "quantum gas", "quantum inform", "quantum scatt","ultracold atom", "ultracold molecul", "quantum noise", "quantum projec", "quantum grav", "quantum phase", "quantum correlati", "quantum entangle",
                "atom interferom", "quantum transport", "quantum imagi", "feshbach resonan", "ultracold gas", "optical clock", "optical lattice clock", "quantum critic", "quantum magnet", "quantum techno", "quantum engineer", "quantum optimi", "quantum financ", "quantum interfer", "quantum gas microsc",
            "quantum key distrib", "quantum encryp", "quantum internet", "quantum photon", "variational quantum", "quantum correl", "quantum syste", "quantum effect", 
                "quantum thermodynamics", "quantum emitter", "quantum fluid", "quantum material", "qkd network", "euroqci", "psot-quantum", "wave function", "quantum diagnostics",
            "non-classical st", "entangled state", "multi-mode enta"]

    prompt_instruction =     """The following description belongs to an EU-funded project. Is the project part of the second quantum revolution? If yes, classify the project by assigning it to one of the following categories: 
        - "quantum computing": A quantum computer is a computer that exploits quantum mechanical phenomena (also quantum simulators), by manipulating quantum bits (qubits) and quantum gates, including firmware, error-correction,readout, diagnostics and characterisation systems, and also software and algorithms. Quantum simulators are devices that actively use quantum effects to answer questions about realizable model systems and, through them, to get results about systems of practical interest (such as superconductors, simulated using arrays of cold atoms). Quantum software refers to software designed to run on quantum computers,  including SDKs and frameworks, programming languages, development tools, orchestration, UI, QaaS, end-user software, cloud, AI and machine learning. This category should also include technologies enabling quantum computing and quantum simulators and building blocks of quantum computers and quantum simulators, if they can be considered a part of the second quantum revolution, e.g. qubits, control electronics, twpa amplifiers.
        - "quantum sensing": The application of quantum systems to constructing more sensitive or more compact sensors of physical properties or fields, such as temperature, distance/displacements, electric or magnetic fields, and also accelerations, rotations, pressure and gravity. Quantum sensing applications also include quantum imaging and lidar. This category should also include technologies enabling quantum sensing and metrology, if they can be considered a part of the second quantum revolution.
        - "quantum communication": communication that uses quantum physics to transmit and protect data, and potentially to enable connections between quantum computers. This category also includes quantum safe protocols and quantum cryptography (quantum key distribution, post quantum cryptography, applications of quantum cryptography), and quantum networking (qubit transfer, modems, transducers, repeaters and memory). This category should also include technologies enabling quantum communication and quantum networks, if they can be considered a part of the second quantum revolution.        
        - "basic science": Basic or fundamental research in quantum science which at some point may be relevant to quantum computing, quantum sensing or quantum communication, and which is part of the second quantum revolution. 

        If the project is not part of the second quantum revolution or if its does not fit into the categories above, classify it as:
        - "not second quantum revolution": This category is for projects which are not related to quantum science or quantum technologies, or which cannot be considered part of the second quantum revolution. It is for all projects which do not fit into the other categories.

        The Second Quantum Revolution refers to the current era of quantum technology advancements, characterized by our ability to manipulate and control individual quantum systems with unprecedented precision. This revolution is defined by the development of technologies that harness quantum phenomena such as superposition and entanglement to create novel applications. Unlike the First Quantum Revolution, which led to (e.g. semicondictor-based) inventions like transistors, lasers based on collective quantum effects, the Second Quantum Revolution focuses on exploiting individual quantum particles and their unique properties.

        Select exactly one category. Only respond with the category name without quotation marks, nothing else!
        
        Please append to the response (after a comma) one of the following keywords describing the platform on which the quantum computer is based: "superconducting", "trapped ion", "neutral atoms", "silicon", "diamond", "photonic", "other". If the platform is not known, please respond with "unknown".

        Please also append to the response (after another comma) a TRL level from 1 to 9.
        
        """

    mapping_dict = {
        "quantum comp": "quantum computing",
        "quantum communication": "quantum communication",
        "quantum sensing": "quantum sensing",
        "basic": "basic science"
    }


    sub_mapping_dict = {
        "superconduct": "superconducting",
        "trapped ion": "trapped ions",
        "neutral atoms": "neutral atoms",
        "silicon": "diamond",
        "photonic": "photonic",
        "other": "other"
    }


    trl_mapping_dict = {
        "9": 9,
        "8": 8,
        "7": 7,
        "6": 6,
        "5": 5,
        "4": 4,
        "3": 3,
        "2": 2,
        "1": 1,
    }


    evaluations = {
        "TotalFundingByFPOverTime": TotalFundingByFPOverTime,
        "TotalFundingByLLMCategoryOverTime": TotalFundingByLLMCategoryOverTime,
        "OrganizationsByCountryGroupOverTime": OrganizationsByCountryGroupOverTime,
        "OrganizationTypeByCountryGroupOverTime": OrganizationTypeByCountryGroupOverTime,
        "TotalFundingbyFP": TotalFundingbyFP
    }

    deliverable_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "C2 Quantum Monitor Deliverables", 
        "message": "Please find the deliverables attached."
    }

    newsletter_email_settings = {
        "sender": "EFMO European Funding Monitor - Quantum technologies", 
        "recipients": ["julian.wienand@ec.europa.eu", "doru.tanasa@ec.europa.eu", "oscar.diez@ec.europa.eu",
                       "Alessio.MAUGERI@ec.europa.eu", "Christian.TREFZGER@ec.europa.eu", "Pascal.MAILLOT@ec.europa.eu", 
                       "Paraskevi.GANOTI@ec.europa.eu", "Albert.GAMITO-GUIJARRO@ec.europa.eu", "j.wienand@aol.com", 
                       "Laurent.OLISLAGER@ec.europa.eu"],
        "subject": "Quantum Monitor Newsletter", 
    }


class hpc_settings:
    topic = "hpc"

    if not os.path.exists(f"data/{topic}"):
        os.makedirs(f"data/{topic}")

    if not os.path.exists(f"deliverables/{topic}"):
        os.makedirs(f"deliverables/{topic}")

    data_source = "f&t"
    filtered_projects_filename= f'data/{topic}/filtered_projects.csv'
    filtered_organizations_filename = f'data/{topic}/filtered_organizations.csv'
    filtered_prev_projects_filename = f'data/{topic}/filtered_projects_prev.csv'
    processed_diff_projects_filename = f'data/{topic}/processed_projects_diff.csv'
    manual_project_data_filename = f'data/{topic}/input_manual_projects.csv'
    manual_orga_data_filename = f'data/{topic}/input_manual_orgas.csv'
    matchscore_histogram_filename = f'data/{topic}/matchscore_histogram.png'

    db_filename = f'deliverables/{topic}/{topic}.db'

    llm_location = "remote"

    suppress_llm_categorization = False
    import_manual_data = False

    send_deliverable = False
    send_newsletter = False

    match_score_threshold = 0.0001



    keyword_list = ["hpc", "parallel processing", "supercomput", "cluster comp", "computer cluster", "computation cluster",
"high-speed interconnect", "petaflop", "quantum comput", "high performance compu"
"complex simulation", "GPU", "cloud comput",
"distributed comput", "fault-tolerance", "resource schedul", "load balanc", "storage array", "quantum algorithm", "quantum emulation", "hybrid CPU-GPU architecture", "NISQ", "error mitigation", "circuit optim",
"quantum-classical hybrid", "parallel algorithm",
"infiniband", "ethernet", "lustre", "gpfs", "quantum parallel"]

    prompt_instruction =     """The following description belongs to an EU-funded project. Is the project related to HPC-systems? If yes, classify the project by assigning it to one of the following categories: 
    - "infrastructure": activities for the acquisition, deployment, upgrading and operation of the secure, hyper-connected world-class supercomputing, quantum computing and data infrastructure, including the promotion of the uptake and systematic use of research and innovation results generated in the Union
    - "federation": activities for providing Union-wide access to federated, secure supercomputing and data resources and services throughout Europe for the research and scientific community, industry, including SMEs, and the public sector
    - "technology": research and innovation activities for developing a world-class, competitive and innovative supercomputing ecosystem across Europe addressing hardware and software technologies, and their integration into computing systems, covering the whole scientific and industrial value chain
    - "applications": activities for achieving and maintaining European excellence in key computing and data applications and codes for science, industry, including SMEs, and the public sector
    - "usage and skills": developing capabilities and skills that foster excellence in supercomputing, quantum computing, and data use, widening the scientific and industrial use of supercomputing resources and data applications
    - "international cooperation": activities relevant to the promotion of international collaboration in supercomputing to solve global scientific and societal challenges, while promoting competitiveness of the European High Performance Computing supply and user ecosystem
    - "ai factories": activities for the provision of an AI-oriented supercomputing service infrastructure that aims to further develop the research and innovation capabilities, competences and skills of the AI ecosystem
    -  "other HPC": It is for all projects which are related to HPC but do not fit into the other categories above.


    If the project is not related to HPC or if its does not fit into the categories above, classify it as:
    - "not HPC": This category is for projects which are not related to HPC systems

    Select exactly one category. Only respond with the category name without quotation marks, nothing else!

    Please append to the response (after a comma) one of the following keywords describing whether the projects involves quantum computing or not: "quantum", "not quantum".

    Please also append to the response (after another comma) a TRL level from 1 to 9.
    
        """

    mapping_dict = {
        "infrastructure": "infrastructure",
        "federation": "federation",
        "technology": "technology",
        "applications": "applications",
        "usage and skills": "usage and skills",
        "international cooperation": "international cooperation",
        "ai factories": "AI factories",
        "other": "other HPC"
    }
    
    sub_mapping_dict = {
        "not": "not quantum",
        "quantum": "quantum",
    }
    
    

    trl_mapping_dict = {
        "9": 9,
        "8": 8,
        "7": 7,
        "6": 6,
        "5": 5,
        "4": 4,
        "3": 3,
        "2": 2,
        "1": 1,
    }




    evaluations = {
        "TotalFundingByFPOverTime": TotalFundingByFPOverTime,
        "TotalFundingByLLMCategoryOverTime": TotalFundingByLLMCategoryOverTime,
        "OrganizationsByCountryGroupOverTime": OrganizationsByCountryGroupOverTime,
        "OrganizationTypeByCountryGroupOverTime": OrganizationTypeByCountryGroupOverTime,
        "TotalFundingbyFP": TotalFundingbyFP
    }

    deliverable_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "C2 Quantum Monitor Deliverables", 
        "message": "Please find the deliverables attached."
    }

    newsletter_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "Quantum Monitor Newsletter", 
    }



class ai_settings:
    topic = "ai"

    if not os.path.exists(f"data/{topic}"):
        os.makedirs(f"data/{topic}")

    if not os.path.exists(f"deliverables/{topic}"):
        os.makedirs(f"deliverables/{topic}")

    data_source = "f&t"
    filtered_projects_filename= f'data/{topic}/filtered_projects.csv'
    filtered_organizations_filename = f'data/{topic}/filtered_organizations.csv'
    filtered_prev_projects_filename = f'data/{topic}/filtered_projects_prev.csv'
    processed_diff_projects_filename = f'data/{topic}/processed_projects_diff.csv'
    manual_project_data_filename = f'data/{topic}/input_manual_projects.csv'
    manual_orga_data_filename = f'data/{topic}/input_manual_orgas.csv'
    matchscore_histogram_filename = f'data/{topic}/matchscore_histogram.png'

    db_filename = f'deliverables/{topic}/{topic}.db'

    llm_location = "remote"

    suppress_llm_categorization = False
    import_manual_data = False

    send_deliverable = False
    send_newsletter = False

    match_score_threshold = 0.5



    keyword_list = ["artificial intelligence", " ai ", "ai,", "machine learning", "deep learning", "natural language processing",  "computer vision", "robot" 
    "supervised learning", "unsupervised learning", "reinforcement learning", 
    "neural network",  "decision trees", "support vector machines", 
    "cluster computing",  "regression", "classification",  "feature engineering", 
    "model evaluation", "convolutional neural network",  "recurrent neural networks", 
    "long short-term memory", "lstm", "generative adversarial network",  "autoencoder", 
    "transfer learning", "backpropagation", "activation functions",  "dropout",
    "batch normalization",  "tokenization", "tkn", "sentiment analysis", "named entity recognition",  
    "machine translation", "text summarization", "language models", "word embedding", 
     "gpt", "text classification",  "image recognition", "object detection", 
    "image segmentation",  "facial recognition",  "optical character recognition", 
    "image generation", "feature extraction",  "augmented reality","pose estimation",
    "path planning", "simultaneous localization and mapping", "autonomous navigation", 
    "robot perception", "human-robot interaction", 
    "q-learning", "markov decision processes","value function",  "reward signal",
    "temporal difference learning", "actor-critic methods","deep q-networks", "dqn", 
    "multi-agent systems", "agentic ai", "bias mitigation",  "ethical ai", 
    "responsible ai",  "ai governance",  "societal impact",  "medical imaging", 
    "predictive analytics",  "personalized medicine", "drug discovery", "health informatics",
    "electronic health records", "diagnostic tools","telemedicine","genomics",
    "clinical decision support","algorithmic trading","fraud detection",  "risk management",
    "credit scoring","portfolio management","predictive analytics","robo-advisors", 
    "sentiment analysis", "market forecasting","financial modeling", "self-driving cars", 
    "drones", "autonomous vehicles", "sensor fusion",  "obstacle detection",
    "real-time processing","safety protocols", "navigation algorithms", 
    "quantum ai", "quantum machine learning", "quantum deep learning",
    "quantum neural network", "qnn", "quantum circuit learning", 
    "quantum reinforcement learning",  "quantum supervised learning",
    "quantum unsupervised learning", "quantum semi-supervised learning", 
    "generative pre-trained transformer", "transformer-xl", "transformer-xl large", "transformer-xl base", 
    "gpt-j", "gpt-neo", "gpt-2xl", "gpt-3xl", "gpt-4", 
    "dall-e", "dall-e mini", "stable diffusion", "stable diffusion model", 
    "latent diffusion", "latent diffusion model", "diffusion-based image synthesis", 
    "text-to-image diffusion", "image-to-text diffusion", "diffusion-based text-to-image synthesis", 
    "llama", "opt-175b", "opt-125b", "opt-66b", 
    "bloom-176b", "bloom-176b-1", "bloom-176b-2", 
    "flan-t5", "flan-t5-3b", "flan-t5-11b"
    ]


    prompt_instruction =     """
    
The following description belongs to an EU-funded project. Is the project related to artificial intelligence? If yes, classify the project by assigning it to one of the following categories:

"machine learning": Projects that focus on algorithms and statistical models that enable computers to perform tasks without explicit instructions, relying on patterns and inference instead. This includes supervised learning, unsupervised learning, reinforcement learning, and deep learning techniques.
"natural language processing": Projects that involve the interaction between computers and human (natural) languages. This encompasses tasks such as language translation, sentiment analysis, speech recognition, and chatbots.
"computer vision": Projects that enable machines to interpret and make decisions based on visual data from the world. This includes image recognition, object detection, video analysis, and facial recognition technologies.
"robotics": Projects that integrate AI with physical robots to perform tasks autonomously or semi-autonomously. This includes robotic process automation, drones, autonomous vehicles, and robotic assistants.
"ai ethics and governance": Projects that address the ethical implications of AI technologies, including fairness, accountability, transparency, and regulatory frameworks for AI deployment.
"other ai": This category is for AI-related projects which do not fit into the categories above. 

If the project is not related to artificial intelligence, classify it as:
"not AI": This category is for projects which are not related to artificial intelligence or which cannot be considered part of AI applications.

Select exactly one category. Only respond with the category name without quotation marks, nothing else!

Please append to the response (after a comma) one of the following keywords describing the application area: "healthcare", "finance", "transportation", "manufacturing", "entertainment", "other". If the application area is not known, please respond with "unknown".

Please also append to the response (after another comma) a TRL level from 1 to 9.
        """

    mapping_dict = {
        "machine learning": "machine learning",
        "language processing": "language processing",
        "computer vision": "computer vision",
        "robotics": "robotics",
        "ethics and governance": "ethics and governance",
        "other ai": "other",
    }
    
    sub_mapping_dict = {
        "healthcare": "healthcare",
        "finance": "finance",
        "transportation": "transportation",
        "manufacturing": "manufacturing",
        "entertainment": "entertainment",
        "other": "other"
    }


    trl_mapping_dict = {
        "9": 9,
        "8": 8,
        "7": 7,
        "6": 6,
        "5": 5,
        "4": 4,
        "3": 3,
        "2": 2,
        "1": 1,
    }



    evaluations = {
        "TotalFundingByFPOverTime": TotalFundingByFPOverTime,
        "TotalFundingByLLMCategoryOverTime": TotalFundingByLLMCategoryOverTime,
        "OrganizationsByCountryGroupOverTime": OrganizationsByCountryGroupOverTime,
        "OrganizationTypeByCountryGroupOverTime": OrganizationTypeByCountryGroupOverTime,
        "TotalFundingbyFP": TotalFundingbyFP
    }

    deliverable_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "C2 Quantum Monitor Deliverables", 
        "message": "Please find the deliverables attached."
    }

    newsletter_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "Quantum Monitor Newsletter", 
    }
    
    
    
    
class cybersecurity_settings:
    topic = "cybersecurity"

    if not os.path.exists(f"data/{topic}"):
        os.makedirs(f"data/{topic}")

    if not os.path.exists(f"deliverables/{topic}"):
        os.makedirs(f"deliverables/{topic}")

    data_source = "f&t"
    filtered_projects_filename= f'data/{topic}/filtered_projects.csv'
    filtered_organizations_filename = f'data/{topic}/filtered_organizations.csv'
    filtered_prev_projects_filename = f'data/{topic}/filtered_projects_prev.csv'
    processed_diff_projects_filename = f'data/{topic}/processed_projects_diff.csv'
    manual_project_data_filename = f'data/{topic}/input_manual_projects.csv'
    manual_orga_data_filename = f'data/{topic}/input_manual_orgas.csv'
    matchscore_histogram_filename = f'data/{topic}/matchscore_histogram.png'

    db_filename = f'deliverables/{topic}/{topic}.db'

    llm_location = "remote"

    suppress_llm_categorization = False
    import_manual_data = False

    send_deliverable = False
    send_newsletter = False

    match_score_threshold = 0.0001



    keyword_list = ["cybersecurit","network securit","information securit","cyber threat","malware","phishing","encryption","firewall","data protect","incident response","penetration test","vulnerability assessment","identity and access management","cloud security","endpoint security","intrusion detection","cyber risk management","security operations center","threat intelligence","zero trust security","ransomware","social engineering","multi-factor authenticat","cyber forensics","siem","compliance and regulation","iot security","artificial intelligence in cybersecurity","blockchain security","quantum cryptography","biometric authentication","ddos protection","data loss prevention","security awareness training","cyber insurance","ethical hacking","devsecops","mobile security","supply chain security","privacy by design", "password", "pqc"]

    prompt_instruction =     """The following description belongs to an EU-funded project. Is the project related to Cybersecurity? If yes, classify the project by assigning it to one of the following categories: 
    - "network security":    Network Security projects focus on protecting network infrastructure and communications. This category includes developing packet sniffers to monitor network traffic, creating firewalls and intrusion detection systems, implementing virtual private networks (VPNs), and conducting network traffic analysis and anomaly detection.
    - "application security":    Application Security projects involve securing software applications and systems. This category encompasses vulnerability assessment and penetration testing of web applications, implementing secure coding practices and code review tools, application-level encryption implementation, and API security testing and implementation.
    - "data protection and encryption":    Data Protection and Encryption projects focus on safeguarding sensitive information. This category includes developing encryption algorithms and protocols, creating data loss prevention (DLP) systems, implementing secure data storage solutions, and designing privacy-enhancing technologies.
    - "threat intelligence and analysis":    Threat Intelligence and Analysis projects involve identifying and analyzing cyber threats. This category covers developing threat intelligence platforms, creating malware analysis tools, implementing security information and event management (SIEM) systems, and designing AI-driven threat detection systems.
    - "identity and access management":    Identity and Access Management projects focus on controlling and monitoring user access to systems and data. This category includes developing multi-factor authentication systems, creating identity verification tools, implementing role-based access control systems, and designing single sign-on (SSO) solutions.
    - "incident response and forensics":    Incident Response and Forensics projects involve preparing for and responding to security incidents. This category encompasses creating incident response playbooks, developing digital forensics tools, designing backup and recovery systems, and implementing security orchestration, automation, and response (SOAR) platforms.
    - "cloud security":    Cloud Security projects focus on securing cloud-based infrastructure and services. This category includes implementing cloud access security brokers (CASBs), developing cloud-native security solutions, creating secure cloud configuration management tools, and designing multi-cloud security strategies.
    - "other cybersecurity": This category is for cybersecurity-related projects which do not fit into the categories above. 

    If the project is not related to Cybersecurity or if its does not fit into the categories above, classify it as:
    - "not cybersecurity": This category is for projects which are not related to Cybersecurity

    Select exactly one category. Only respond with the category name without quotation marks, nothing else!

    Please append to the response (after a comma) one of the following keywords describing whether the projects involves quantum computing or not: "quantum", "not quantum".

    Please also append to the response (after another comma) a TRL level from 1 to 9.
    
        """

    mapping_dict = {
        "network security": "network security",
        "application security": "application security",
        "data protection and encryption": "data protection and encryption",
        "threat intelligence and analysis": "threat intelligence and analysis",
        "identity and access management": "identity and access management",
        "incident response and forensics": "incident response and forensics",
        "cloud security": "cloud security",
        "other": "other cybersecurity"
    }
    
    sub_mapping_dict = {
        "not": "not quantum",
        "quantum": "quantum",
    }
    
    

    trl_mapping_dict = {
        "9": 9,
        "8": 8,
        "7": 7,
        "6": 6,
        "5": 5,
        "4": 4,
        "3": 3,
        "2": 2,
        "1": 1,
    }




    evaluations = {
        "TotalFundingByFPOverTime": TotalFundingByFPOverTime,
        "TotalFundingByLLMCategoryOverTime": TotalFundingByLLMCategoryOverTime,
        "OrganizationsByCountryGroupOverTime": OrganizationsByCountryGroupOverTime,
        "OrganizationTypeByCountryGroupOverTime": OrganizationTypeByCountryGroupOverTime,
        "TotalFundingbyFP": TotalFundingbyFP
    }

    deliverable_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "C2 Quantum Monitor Deliverables", 
        "message": "Please find the deliverables attached."
    }

    newsletter_email_settings = {
        "sender": "CNECT.C2 QUANTUM MONITOR", 
        "recipients": ["julian.wienand@ec.europa.eu"],
        "subject": "Quantum Monitor Newsletter", 
    }



    