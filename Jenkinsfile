pipeline {
    agent any

    triggers {
        cron('* * * * *')
    }

    options {
        buildDiscarder(logRotator(numToKeepStr: '50'))
        disableConcurrentBuilds()
    }

    stages {
        stage('Pull Telemetry & Push to MongoDB') {
            steps {
                echo '=== Running Lab 6 SDN Telemetry Ingestion Pipeline ==='
                sh '''
                    python3 /home/dheeraj/softwareDefinedNetwork/lab6/pull_and_push_mongo.py
                '''
            }
        }
    }

    post {
        success {
            echo '[+] Successfully ingested telemetry snapshot into MongoDB (sdn_lab6.telemetry).'
        }
        failure {
            echo '[!] Failed to ingest telemetry snapshot into MongoDB.'
        }
    }
}
