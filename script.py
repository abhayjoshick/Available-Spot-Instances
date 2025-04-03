import boto3
import csv

def get_all_regions():
    """
    Retrieves a list of all regions (only those that are opted in).
    """
    ec2_client = boto3.client('ec2', region_name='us-east-1')
    response = ec2_client.describe_regions(AllRegions=True)
    regions = [r['RegionName'] for r in response['Regions'] if r['OptInStatus'] != 'not-opted-in']
    return regions

def get_spot_offerings_for_region(region):
    """
    Retrieves all instance type offerings available as Spot instances in the given region,
    with each offering tied to an Availability Zone.
    """
    ec2_client = boto3.client('ec2', region_name=region)
    offerings = []
    paginator = ec2_client.get_paginator('describe_instance_type_offerings')
    for page in paginator.paginate(LocationType='availability-zone'):
        offerings.extend(page['InstanceTypeOfferings'])
    return offerings

def get_instance_type_details(region, instance_types):
    """
    Retrieves detailed specs for a batch of instance types in the given region.
    Returns a dictionary mapping instance type to its specs.
    """
    ec2_client = boto3.client('ec2', region_name=region)
    details = {}
    # Process in batches of 100 to avoid API limits
    for i in range(0, len(instance_types), 100):
        batch = instance_types[i:i+100]
        response = ec2_client.describe_instance_types(InstanceTypes=batch)
        for inst in response['InstanceTypes']:
            inst_type = inst['InstanceType']
            vcpus = inst['VCpuInfo']['DefaultVCpus']
            # Memory is given in MiB; convert to GiB
            memory = inst['MemoryInfo']['SizeInMiB'] / 1024
            details[inst_type] = {'vcpus': vcpus, 'memory': memory}
    return details

def main():
    # Get user inputs for exact filtering
    exact_vcpus = int(input("Enter exact number of vCPUs: "))
    exact_memory = float(input("Enter exact memory (GiB): "))
    output_file = 'available_spot_instances.csv'
    
    regions = get_all_regions()
    all_results = []
    
    # Loop through each region
    for region in regions:
        print(f"Processing region: {region}")
        try:
            offerings = get_spot_offerings_for_region(region)
        except Exception as e:
            print(f"Error processing region {region}: {e}")
            continue
        
        # Create a mapping: instance type -> list of AZs where it's offered
        instance_type_to_azs = {}
        for offer in offerings:
            inst_type = offer['InstanceType']
            az = offer['Location']
            if inst_type in instance_type_to_azs:
                if az not in instance_type_to_azs[inst_type]:
                    instance_type_to_azs[inst_type].append(az)
            else:
                instance_type_to_azs[inst_type] = [az]
        
        # Get unique instance types offered in the region
        instance_types_list = list(instance_type_to_azs.keys())
        try:
            details = get_instance_type_details(region, instance_types_list)
        except Exception as e:
            print(f"Error getting instance details for region {region}: {e}")
            continue
        
        # Filter instance types based on exact vCPUs and memory
        for inst_type, spec in details.items():
            if spec['vcpus'] == exact_vcpus and spec['memory'] == exact_memory:
                azs = instance_type_to_azs.get(inst_type, [])
                for az in azs:
                    row = {
                        'instance_type': inst_type,
                        'vcpus': spec['vcpus'],
                        'ram': spec['memory'],
                        'region': region,
                        'az': az
                    }
                    all_results.append(row)
    
    # Write the results to a CSV file
    fieldnames = ['instance_type', 'vcpus', 'ram', 'region', 'az']
    with open(output_file, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_results:
            writer.writerow(row)
    
    print(f"Results written to {output_file}")

if __name__ == '__main__':
    main()
