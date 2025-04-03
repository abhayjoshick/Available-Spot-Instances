import boto3
import json

def get_all_instance_types():
    ec2_client = boto3.client('ec2')
    instance_types = []
    paginator = ec2_client.get_paginator('describe_instance_types')
    for page in paginator.paginate():
        for instance_type in page['InstanceTypes']:
            instance_types.append(instance_type['InstanceType'])
    return instance_types

def filter_instance_types_by_resources(instance_types, min_vcpus, min_memory_gib):
    ec2_client = boto3.client('ec2')
    filtered_types = []
    for i in range(0, len(instance_types), 100):
        batch = instance_types[i:i+100]
        response = ec2_client.describe_instance_types(InstanceTypes=batch)
        for instance_type_info in response['InstanceTypes']:
            vcpus = instance_type_info['VCpuInfo']['DefaultVCpus']
            memory_gib = instance_type_info['MemoryInfo']['SizeInMiB'] / 1024
            if vcpus >= min_vcpus and memory_gib >= min_memory_gib:
                filtered_types.append(instance_type_info['InstanceType'])
    return filtered_types

def check_spot_availability(instance_types):
    ec2_client = boto3.client('ec2')
    available_spot_types = []
    for i in range(0, len(instance_types), 200):
        batch = instance_types[i:i+200]
        response = ec2_client.describe_instance_type_offerings(
            LocationType='region',
            Filters=[{'Name': 'instance-type', 'Values': batch}]
        )
        for offering in response['InstanceTypeOfferings']:
            available_spot_types.append(offering['InstanceType'])
    return available_spot_types

def main(min_vcpus, min_memory_gib, output_file):
    all_instance_types = get_all_instance_types()
    filtered_types = filter_instance_types_by_resources(all_instance_types, min_vcpus, min_memory_gib)
    available_spot_types = check_spot_availability(filtered_types)
    with open(output_file, 'w') as f:
        json.dump(available_spot_types, f, indent=4)
    print(f"Available spot instance types saved to {output_file}")

if __name__ == "__main__":
    min_vcpus = int(input("Enter minimum number of vCPUs: "))
    min_memory_gib = int(input("Enter minimum memory (GiB): "))
    output_file = 'available_spot_instances.json'
    main(min_vcpus, min_memory_gib, output_file)
