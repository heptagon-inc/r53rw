from aws_cdk import (
    core,
    aws_s3 as s3,
    aws_cloudtrail as cloudtrail,
    aws_logs as logs,
    aws_events as events,
    aws_events_targets as targets,
    aws_codebuild as codebuild,
    aws_iam as iam,
    aws_lambda as lambda_,
)
import boto3


ssm_client = boto3.client('ssm')
response = ssm_client.get_parameters(
    Names=[
        'r53rw_ID',
        'r53rw_HOSTED_ZONE_ID',
        'r53rw_HOSTED_ZONE_NAME',
    ],
    WithDecryption=True
)
params = {}
for param in response['Parameters']:
    params[param['Name']] = param['Value']

ID = params['r53rw_ID']
HOSTED_ZONE_ID = params['r53rw_HOSTED_ZONE_ID']
HOSTED_ZONE_NAME = params['r53rw_HOSTED_ZONE_NAME']


class R53RwStack(core.Stack):
    def __init__(self, scope: core.Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        mybucket = s3.Bucket(
            self,
            ID+'-bucket',
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            lifecycle_rules=[
                s3.LifecycleRule(
                    enabled=True,
                    noncurrent_version_expiration=core.Duration.days(30),
                )
            ])

        cloudtrail.Trail(
            self,
            ID+'-trail',
            enable_file_validation=True,
            include_global_service_events=True,
            is_multi_region_trail=True,
            send_to_cloud_watch_logs=True,
            cloud_watch_logs_retention=logs.RetentionDays.ONE_WEEK,
        )

        func_diff_notice = lambda_.Function(
            self,
            ID+'-func_diff_notice',
            code=lambda_.Code.asset('./functions/artifacts/'),
            handler='app.diff_notice',
            runtime=lambda_.Runtime.PYTHON_3_7,
            log_retention=logs.RetentionDays.ONE_MONTH,
            memory_size=128,
            timeout=core.Duration.seconds(60),
            tracing=lambda_.Tracing.ACTIVE
        )
        func_diff_notice.add_to_role_policy(
            iam.PolicyStatement(
                actions=['ssm:GetParameter'],
                resources=['*'],
            )
        )

        func_codebuild_alert = lambda_.Function(
            self,
            ID+'-func_codebuild_alert',
            code=lambda_.Code.asset('./functions/artifacts/'),
            handler='app.codebuild_alert',
            runtime=lambda_.Runtime.PYTHON_3_7,
            log_retention=logs.RetentionDays.ONE_MONTH,
            memory_size=128,
            timeout=core.Duration.seconds(60),
            tracing=lambda_.Tracing.ACTIVE
        )
        func_codebuild_alert.add_to_role_policy(
            iam.PolicyStatement(
                actions=['ssm:GetParameter'],
                resources=['*'],
            )
        )

        codebuild_project = codebuild.Project(
            self,
            ID+'-codebuild-project',
            environment=codebuild.BuildEnvironment(
                build_image=codebuild.LinuxBuildImage.STANDARD_2_0,
                compute_type=codebuild.ComputeType.SMALL
            ),
            build_spec=codebuild.BuildSpec.from_object({
                'version': 0.2,
                'phases': {
                    'install': {
                        'runtime-versions': {
                            'ruby': 2.6
                        },
                        'commands': [
                            'gem install roadworker'
                        ]
                    },
                    'build': {
                        'commands': [
                            'roadwork --export --target-zone '+HOSTED_ZONE_NAME+' --output Routefile',
                            'aws s3 cp Routefile s3://'+mybucket.bucket_name + '/Routefile'
                        ]
                    }
                }
            })
        )
        codebuild_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=['s3:putObject'],
                resources=[mybucket.bucket_arn+'/Routefile'],
            )
        )
        codebuild_project.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    'route53:List*',
                    'route53:Get*'
                ],
                resources=['*'],
            )
        )
        codebuild_project.on_build_failed(
            ID+'-rule-on_build_failed',
            target=targets.LambdaFunction(func_codebuild_alert))

        rule = events.Rule(
            self,
            ID+'-rule',
            enabled=True
        )
        rule.add_event_pattern(
            source=[
                'aws.route53'
            ],
            detail_type=[
                'AWS API Call via CloudTrail'
            ],
            detail={
                'eventSource': [
                    'route53.amazonaws.com'
                ],
                'eventName': [
                    'ChangeResourceRecordSets'
                ],
                'requestParameters': {
                    'hostedZoneId': [
                        HOSTED_ZONE_ID
                    ]
                },
            },
        )
        rule.add_target(targets.LambdaFunction(func_diff_notice))
        rule.add_target(targets.CodeBuildProject(codebuild_project))
