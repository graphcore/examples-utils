SELECT DATE_TRUNC('day', create_date) AS create_date,
       CASE
           WHEN (NOT runtime_failed) THEN runtime_state
           WHEN (runtime_error LIKE 'The node was low on resource%'
                 AND runtime_state = 'Node Died') THEN 'insufficient_storage'
           WHEN (runtime_error LIKE 'Notebook was terminated early'
                 AND runtime_state = 'Node Died') THEN 'undiagnosed - node_terminated_early'
           WHEN (runtime_error LIKE 'Exceeded timeout of 60 seconds waiting for readiness%'
                 AND runtime_state = 'Exit Code != 0') THEN CASE
                                                                WHEN (runtime_error LIKE 'Exceeded timeout of 60 seconds waiting for readiness%[integrations-sidecar]%'
                                                                      AND run_duration_seconds > 120) THEN 'undiagnosed - container_sidecar_failed_restart'
                                                                WHEN (runtime_error LIKE 'Exceeded timeout of 60 seconds waiting for readiness%[integrations-sidecar]%') THEN 'undiagnosed - container_sidecar_not_ready' -- this error does not appear with the new filters

                                                                WHEN (container_name LIKE '%2.6.0-ubuntu%'
                                                                      OR container_name LIKE '%3.0.0-ubuntu%'
                                                                      OR container_name LIKE '%3.1.0-ubuntu%') THEN 'undiagnosed - old_container_not_ready'
                                                                WHEN (NOT (repository LIKE '%graphcore/%'
                                                                           OR repository LIKE '%graphcore-research/%'
                                                                           OR repository LIKE '%/Graphcore-%')) THEN 'undiagnosed - external_repo_not_ready'
                                                                ELSE 'undiagnosed - jupyter_not_ready'
                                                            END
           WHEN (runtime_error LIKE 'Error downloading workspace%'
                 AND runtime_state = 'Exit Code != 0') THEN 'bad_repo_url'
           WHEN (runtime_error LIKE 'Failed to pull image%'
                 AND runtime_state = 'Exit Code != 0') THEN CASE
                                                                WHEN (container_name='graphcore/pytorch-geometric-jupyter:2-amd-3.2.0-ubuntu-20.04-20230314') THEN 'bad_container_in_pyg_link'
                                                                ELSE 'failed_to_pull_docker_image'
                                                            END
           WHEN (runtime_error LIKE 'Exceeded timeout of 45 seconds waiting for provisioning%'
                 AND runtime_state = 'System Error') THEN 'out_of_capacity'
           WHEN (runtime_error LIKE 'Crash back off%'
                 AND runtime_state = 'Exit Code != 0') THEN CASE
                                                                WHEN (RIGHT(RTRIM(runtime_error), 3) = '255') THEN 'gc_monitor_failed'
                                                                WHEN (NOT (repository LIKE '%/Gradient-%'
                                                                           OR repository LIKE '%/Graphcore-%')
                                                                      AND runtime_error LIKE '%code 127') THEN 'missing_setup_script_in_repo'
                                                                WHEN (runtime_error LIKE '%/notebooks/setup.sh % test%') THEN 'failed_test_run'
                                                                WHEN (NOT (repository LIKE '%graphcore/%'
                                                                           OR repository LIKE '%graphcore-research/%'
                                                                           OR repository LIKE '%/Graphcore-%')) THEN 'undiagnosed - external_repo_not_ready'
                                                                WHEN (runtime_error LIKE 'Crash back off:%apt update%')
                                                                     OR (runtime_error LIKE 'Crash back off:%apt install%') THEN 'suspicious_user_behaviour'
                                                                WHEN (runtime_error LIKE '%setup.sh%exited with code 127') THEN 'undiagnosed - setup_script_missing_in_GC_repo'
                                                                WHEN (runtime_error LIKE '%setup.sh%exited with code 126') THEN 'undiagnosed - setup_script_not_executable_in_GC_repo'
                                                                ELSE 'unclassified - ' + RIGHT(RTRIM(runtime_error), 8)
                                                            END
           ELSE 'unclassified - ' + runtime_state
       END AS known_errors,
       COUNT(*) AS count
FROM mkt_sdk_data.paperspace_use
WHERE abuse_user IN (false)
  AND internal_user IN (false)
  AND date::timestamptz >= '2023-05-15 13:24:16.000000'
  AND date::timestamptz < '2023-06-06 13:24:16.000000'
  AND runs_flag = true
  AND abuse_user = false
  AND runtime_failed = true
GROUP BY DATE_TRUNC('day', create_date),
         CASE
             WHEN (NOT runtime_failed) THEN runtime_state
             WHEN (runtime_error LIKE 'The node was low on resource%'
                   AND runtime_state = 'Node Died') THEN 'insufficient_storage'
             WHEN (runtime_error LIKE 'Notebook was terminated early'
                   AND runtime_state = 'Node Died') THEN 'undiagnosed - node_terminated_early'
             WHEN (runtime_error LIKE 'Exceeded timeout of 60 seconds waiting for readiness%'
                   AND runtime_state = 'Exit Code != 0') THEN CASE
                                                                  WHEN (runtime_error LIKE 'Exceeded timeout of 60 seconds waiting for readiness%[integrations-sidecar]%'
                                                                        AND run_duration_seconds > 120) THEN 'undiagnosed - container_sidecar_failed_restart'
                                                                  WHEN (runtime_error LIKE 'Exceeded timeout of 60 seconds waiting for readiness%[integrations-sidecar]%') THEN 'undiagnosed - container_sidecar_not_ready' -- this error does not appear with the new filters

                                                                  WHEN (container_name LIKE '%2.6.0-ubuntu%'
                                                                        OR container_name LIKE '%3.0.0-ubuntu%'
                                                                        OR container_name LIKE '%3.1.0-ubuntu%') THEN 'undiagnosed - old_container_not_ready'
                                                                  WHEN (NOT (repository LIKE '%graphcore/%'
                                                                             OR repository LIKE '%graphcore-research/%'
                                                                             OR repository LIKE '%/Graphcore-%')) THEN 'undiagnosed - external_repo_not_ready'
                                                                  ELSE 'undiagnosed - jupyter_not_ready'
                                                              END
             WHEN (runtime_error LIKE 'Error downloading workspace%'
                   AND runtime_state = 'Exit Code != 0') THEN 'bad_repo_url'
             WHEN (runtime_error LIKE 'Failed to pull image%'
                   AND runtime_state = 'Exit Code != 0') THEN CASE
                                                                  WHEN (container_name='graphcore/pytorch-geometric-jupyter:2-amd-3.2.0-ubuntu-20.04-20230314') THEN 'bad_container_in_pyg_link'
                                                                  ELSE 'failed_to_pull_docker_image'
                                                              END
             WHEN (runtime_error LIKE 'Exceeded timeout of 45 seconds waiting for provisioning%'
                   AND runtime_state = 'System Error') THEN 'out_of_capacity'
             WHEN (runtime_error LIKE 'Crash back off%'
                   AND runtime_state = 'Exit Code != 0') THEN CASE
                                                                  WHEN (RIGHT(RTRIM(runtime_error), 3) = '255') THEN 'gc_monitor_failed'
                                                                  WHEN (NOT (repository LIKE '%/Gradient-%'
                                                                             OR repository LIKE '%/Graphcore-%')
                                                                        AND runtime_error LIKE '%code 127') THEN 'missing_setup_script_in_repo'
                                                                  WHEN (runtime_error LIKE '%/notebooks/setup.sh % test%') THEN 'failed_test_run'
                                                                  WHEN (NOT (repository LIKE '%graphcore/%'
                                                                             OR repository LIKE '%graphcore-research/%'
                                                                             OR repository LIKE '%/Graphcore-%')) THEN 'undiagnosed - external_repo_not_ready'
                                                                  WHEN (runtime_error LIKE 'Crash back off:%apt update%')
                                                                       OR (runtime_error LIKE 'Crash back off:%apt install%') THEN 'suspicious_user_behaviour'
                                                                  WHEN (runtime_error LIKE '%setup.sh%exited with code 127') THEN 'undiagnosed - setup_script_missing_in_GC_repo'
                                                                  WHEN (runtime_error LIKE '%setup.sh%exited with code 126') THEN 'undiagnosed - setup_script_not_executable_in_GC_repo'
                                                                  ELSE 'unclassified - ' + RIGHT(RTRIM(runtime_error), 8)
                                                              END
             ELSE 'unclassified - ' + runtime_state
         END
ORDER BY count DESC
LIMIT 250;